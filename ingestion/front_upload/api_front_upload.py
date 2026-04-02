import os
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from botocore.client import Config
from fastapi.middleware.cors import CORSMiddleware
import boto3
import uvicorn
from dotenv import load_dotenv

# 1. Environment var loading
load_dotenv()

app = FastAPI(title="EUFactForce API")

# 2. Dash-app URL
origins = [
    "http://localhost:8050",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. S3 instancing
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"),
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
    config=Config(s3={'addressing_style': 'path'}) # <-- Ajoute cette ligne impérativement
)

BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")

# API print debugging
try:
    s3_client.create_bucket(Bucket=BUCKET_NAME)
    print(f"Bucket '{BUCKET_NAME}' créé ou déjà existant.")
except Exception as e:
    print(f"Note: Le bucket existe peut-être déjà : {e}")

@app.get("/")
async def root():
    return {"message": "API EUFactForce opérationnelle"}

# 4. Upload routine
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    metadata: str = Form(...)
):
    try:
        # filename cleanup
        filename = file.filename
        json_filename = f"{os.path.splitext(filename)[0]}.json"

        # A. PDF upload on S3
        file_content = await file.read()
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=file_content,
            ContentType="application/pdf"
        )

        # B. JSON Metadatas S3 upload
        # Json type check
        try:
            json_data = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Métadonnées JSON invalides")

        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=json_filename,
            Body=json.dumps(json_data),
            ContentType="application/json"
        )

        return {
            "status": "success",
            "message": f"Fichiers {filename} et {json_filename} téléchargés avec succès."
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Uvicorn server exposition on 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)
