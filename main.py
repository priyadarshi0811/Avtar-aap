from fastapi import FastAPI, UploadFile, File, HTTPException, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import os
import shutil
import uuid
from datetime import datetime
import subprocess
import asyncio
import sys
import traceback
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Utility: 
def process_Avatar_Gen(audio_path: str, source_image: str, output_dir: str) -> str:
    """
    Processes an entire audio file with Avatar Gen to produce a talking-head video.
    Returns the absolute path to the generated video file.
    """
    try:
        logger.info(f"Processing Avatar Gen with audio: {audio_path}, image: {source_image}")
        
        audio_abs = os.path.abspath(audio_path)
        img_abs   = os.path.abspath(source_image)
        os.makedirs(output_dir, exist_ok=True)
        
        # Check if input files exist
        if not os.path.exists(audio_abs):
            raise Exception(f"Audio file not found: {audio_abs}")
        if not os.path.exists(img_abs):
            raise Exception(f"Image file not found: {img_abs}")
        
        out_name = f"{os.path.splitext(os.path.basename(audio_path))[0]}_Avatar_Gen.mp4"
        out_abs  = os.path.abspath(os.path.join(output_dir, out_name))

        # Check multiple possible Avatar Gen locations
        possible_Avatar_Gen_paths = [
            "/content/main/Avatar_GEN",
            "./Avatar_GEN",
            "../Avatar_GEN",
            os.path.join(os.getcwd(), "Avatar_GEN"),
        ]
        
        Avatar_Gen_root = None
        for path in possible_Avatar_Gen_paths:
            if os.path.exists(path):
                Avatar_Gen_root = os.path.abspath(path)
                break
        
        if not Avatar_Gen_root:
            raise Exception(f"Avatar_Gen SDK not found in any of these paths: {possible_Avatar_Gen_paths}. Please ensure it's cloned correctly.")
        
        logger.info(f"Using Avatar_Gen SDK from: {Avatar_Gen_root}")
        
        if Avatar_Gen_root not in sys.path:
            sys.path.insert(0, Avatar_Gen_root)
        
        try:
            # Dynamically import StreamSDK and run only when needed
            from inference import StreamSDK, run
        except ImportError as e:
            raise Exception(f"Cannot import Avatar_Gen SDK modules from {Avatar_Gen_root}. Ensure inference.py is accessible and dependencies are installed. Error: {e}")

        # Check for checkpoints
        # The new structure suggests checkpoints are inside Avatar_GEN directly
        checkpoints = os.path.join(Avatar_Gen_root, "checkpoints/jetson_trt")
        cfg_pkl = os.path.join(Avatar_Gen_root, "checkpoints/cfg/v0.4_hubert_cfg_trt.pkl")
        
        if not os.path.exists(checkpoints):
            raise Exception(f"Checkpoints directory not found: {checkpoints}. Please ensure 'Avatar_GEN/checkpoints/jetson_trt' exists.")
        if not os.path.exists(cfg_pkl):
            raise Exception(f"Config file not found: {cfg_pkl}. Please ensure 'Avatar_GEN/checkpoints/cfg/v0.4_hubert_cfg_trt.pkl' exists.")

        # Initialize SDK
        logger.info("Initializing Avatar_Gen SDK...")
        sdk = StreamSDK(cfg_pkl, checkpoints)

        # Run inference
        logger.info("Running Avatar_Gen inference...")
        # The 'run' function is synchronous, so it's run in an executor by the caller
        run(sdk, audio_abs, img_abs, out_abs)

        if not os.path.exists(out_abs):
            raise Exception("Output video not created by Avatar_Gen SDK after inference.")
        
        logger.info(f"Successfully generated video: {out_abs}")
        return out_abs
        
    except Exception as e:
        logger.error(f"Avatar_Gen processing error: {str(e)}")
        # Re-raise the exception with a more descriptive message for the client
        raise Exception(f"Avatar_Gen SDK processing failed: {str(e)}")

# FastAPI application setup
app = FastAPI(title="AI Avatar Studio API", version="1.0.0")

# Global exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """
    Handles FastAPI's HTTPException, returning a consistent JSON error response.
    """
    logger.error(f"HTTP Exception: {exc.detail} - Status Code: {exc.status_code}")
    return JSONResponse({"success": False, "message": exc.detail}, status_code=exc.status_code)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Catches any unhandled exceptions, logs them, and returns a generic 500 error.
    """
    tb = traceback.format_exc()
    logger.error(f"Unhandled error for request: {request.url} - {tb}")
    return JSONResponse({"success": False, "message": "Internal Server Error", "detail": "An unexpected error occurred. Please try again later."}, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure necessary directories exist
for d in ["uploads", "generated", "pushed", "static"]:
    os.makedirs(d, exist_ok=True)
    logger.info(f"Directory ensured: {d}")

# Mount static file directories
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/generated", StaticFiles(directory="generated"), name="generated")

# In-memory storage of avatar metadata (for demonstration purposes, not persistent)
generated_avatars = []
pushed_avatars = []

@app.get("/")
async def serve_frontend():
    """Serves the main HTML frontend file."""
    return FileResponse("static/index.html")

@app.post("/api/generate-avatar")
async def generate_avatar(
    audio_file: UploadFile = File(...),
    media_file: UploadFile = File(...)
):
    """
    Generates an avatar video from an uploaded audio file and an image file
    using the Avatar_Gen TalkingHead model.
    """
    logger.info(f"Received avatar generation request - Audio: {audio_file.filename}, Media: {media_file.filename}")
    
    # Validate upload types and presence of files
    if not audio_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No audio file uploaded.")
    if not media_file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No media file uploaded.")

    if not audio_file.content_type or not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid audio file type. Expected 'audio/*', Got: {audio_file.content_type}")
    if not media_file.content_type or not media_file.content_type.startswith('image/'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid media file type. Expected 'image/*', Got: {media_file.content_type}. (Ditto model currently only supports images.)")

    avatar_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    uploaddir, gen_dir = "uploads", "generated"
    
    # Ensure file extensions are present for saving and processing
    audio_ext = os.path.splitext(audio_file.filename)[1] or '.wav'
    media_ext = os.path.splitext(media_file.filename)[1] or '.jpg'
    
    audio_path = os.path.join(uploaddir, f"{avatar_id}_audio{audio_ext}")
    img_path   = os.path.join(uploaddir, f"{avatar_id}_media{media_ext}")

    try:
        # Save uploaded files asynchronously
        logger.info(f"Saving audio to: {audio_path}")
        with open(audio_path, "wb") as af:
            content = await audio_file.read()
            af.write(content)
        
        logger.info(f"Saving image to: {img_path}")
        with open(img_path, "wb") as mf:
            content = await media_file.read()
            mf.write(content)
        
        # Verify files were saved by checking their existence and size
        if not os.path.exists(audio_path) or os.path.getsize(audio_path) == 0:
            raise Exception(f"Failed to save audio file or file is empty at {audio_path}")
        if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
            # Clean up audio file if image saving fails
            if os.path.exists(audio_path): os.remove(audio_path)
            raise Exception(f"Failed to save image file or file is empty at {img_path}")
        
        logger.info(f"Files saved successfully. Audio size: {os.path.getsize(audio_path)} bytes, Image size: {os.path.getsize(img_path)} bytes.")

        # Process with Avatar_Gen in a thread pool executor to avoid blocking the event loop
        logger.info("Starting Avatar_Gen processing in a background thread...")
        output_path = await asyncio.get_event_loop().run_in_executor(
            None, process_Avatar_Gen, audio_path, img_path, gen_dir
        )
        
        logger.info(f"Avatar_Gen processing completed. Output video: {output_path}")

    except HTTPException:
        # Re-raise explicit HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Error during avatar generation process: {str(e)}")
        # Clean up any files that might have been saved before the error
        for p in [audio_path, img_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                    logger.warning(f"Cleaned up temporary file: {p}")
                except OSError as cleanup_e:
                    logger.error(f"Error during cleanup of {p}: {cleanup_e}")
        # Raise a generic 500 error if it's not already an HTTPException
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Avatar generation failed: {str(e)}")
    
    finally:
        # Optional: Remove uploaded files even on success. Commented out as per original provided code.
        # If you uncomment this, ensure 'output_path' variable is defined before this block.
        # try:
        #     if os.path.exists(audio_path):
        #         os.remove(audio_path)
        #     if os.path.exists(img_path):
        #         os.remove(img_path)
        # except Exception as e:
        #     logger.warning(f"Failed to cleanup uploaded files: {e}")
        pass # Using pass to indicate intentional empty finally block if cleanup is commented out

    # Record generated avatar metadata
    avatar = {
        "id": avatar_id,
        "filename": os.path.basename(output_path),
        "original_audio": audio_file.filename,
        "original_media": media_file.filename,
        "created_at": timestamp,
        "url": f"/generated/{os.path.basename(output_path)}"
    }
    generated_avatars.append(avatar)
    logger.info(f"Avatar generated successfully and metadata stored: {avatar_id}")
    return {"success": True, "avatar": avatar}

@app.get("/api/generated-avatars")
async def list_generated():
    """Returns a list of all generated avatar metadata."""
    logger.info("Serving list of generated avatars.")
    return {"success": True, "avatars": generated_avatars}

@app.post("/api/push-avatar/{avatar_id}")
async def push_avatar(avatar_id: str):
    """
    Moves an avatar from the 'generated' list to the 'pushed' list.
    """
    logger.info(f"Attempting to push avatar: {avatar_id}")
    for i, a in enumerate(generated_avatars):
        if a["id"] == avatar_id:
            avatar = generated_avatars.pop(i)
            avatar["pushed_at"] = datetime.now().isoformat()
            pushed_avatars.append(avatar)
            logger.info(f"Avatar {avatar_id} pushed successfully.")
            return {"success": True, "avatar": avatar}
    logger.warning(f"Push failed: Avatar {avatar_id} not found in generated list.")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found in generated list.")

@app.get("/api/pushed-avatars")
async def list_pushed():
    """Returns a list of all pushed avatar metadata."""
    logger.info("Serving list of pushed avatars.")
    return {"success": True, "avatars": pushed_avatars}

@app.delete("/api/avatar/{avatar_id}")
async def delete_avatar(avatar_id: str):
    """
    Deletes an avatar from either the generated or pushed list
    and removes its corresponding video file.
    """
    logger.info(f"Attempting to delete avatar: {avatar_id}")
    for coll in (generated_avatars, pushed_avatars):
        for i, a in enumerate(coll):
            if a["id"] == avatar_id:
                removed = coll.pop(i)
                fp = os.path.join("generated", removed["filename"])
                if os.path.exists(fp):
                    try:
                        os.remove(fp)
                        logger.info(f"Successfully deleted video file: {fp}")
                    except OSError as e:
                        logger.error(f"Failed to delete video file {fp}: {e}")
                        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete avatar file: {e}")
                else:
                    logger.warning(f"Video file {fp} not found during deletion of avatar {avatar_id}.")
                logger.info(f"Avatar {avatar_id} deleted successfully from list.")
                return {"success": True, "message": "Avatar deleted."}
    logger.warning(f"Delete failed: Avatar {avatar_id} not found in any list.")
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Avatar not found.")

@app.get("/api/health")
async def health():
    """Provides a health check endpoint for the API."""
    logger.debug("Health check requested.")
    # Check if Avatar_Gen SDK is initialized (though not directly here, via `process_Avatar_Gen` init on first call)
    # For a direct health check of Avatar_Gen SDK readiness, you might need a global flag
    # controlled by process_Avatar_Gen or avatar_processor, but the current structure implies it's
    # initialized on first run of process_Avatar_Gen.
    return {"status": "healthy", "generated_count": len(generated_avatars), "pushed_count": len(pushed_avatars)}

# Debug endpoint to check file system
@app.get("/api/debug/files")
async def debug_files():
    """
    Provides debugging information about the server's file system,
    listing directories and their contents.
    """
    logger.info("Debug files endpoint accessed.")
    debug_info = {}
    for directory in ["uploads", "generated", "pushed", "static"]:
        full_path = os.path.abspath(directory)
        if os.path.exists(full_path):
            files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
            debug_info[directory] = {
                "exists": True,
                "path": full_path,
                "files": files,
                "count": len(files)
            }
        else:
            debug_info[directory] = {"exists": False, "path": full_path}
    
    # Add Avatar_Gen root path check for debugging model availability
    Avatar_Gen_root_found = False
    possible_Avatar_Gen_paths = [
        "/content/main/Avatar_GEN",
        "./Avatar_GEN",
        "../Avatar_GEN",
        os.path.join(os.getcwd(), "Avatar_GEN"),
        "Avatar_Gen" 
    ]
    for path in possible_Avatar_Gen_paths:
        if os.path.exists(os.path.abspath(path)):
            debug_info["Avatar_Gen_sdk_root"] = {"exists": True, "path": os.path.abspath(path)}
            Avatar_Gen_root_found = True
            break
    if not Avatar_Gen_root_found:
        debug_info["Avatar_Gen_sdk_root"] = {"exists": False, "message": "Avatar_Gen SDK root not found in common locations."}

    return {"success": True, "directories": debug_info}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8506, log_level="info")
