import os
import json
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from botocore.client import Config
from fastapi.middleware.cors import CORSMiddleware
import boto3
import uvicorn
from dotenv import load_dotenv

# 1. Chargement des variables d'environnement
load_dotenv()

app = FastAPI(title="EUFactForce API")

# 2. Configuration des CORS
# Adapte l'URL selon le port de ton frontend (Streamlit, Dash, etc.)
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



# 3. Configuration Client S3 (LocalStack ou AWS)
s3_client = boto3.client(
    "s3",
    endpoint_url=os.getenv("AWS_S3_ENDPOINT_URL"), # Crucial pour LocalStack
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),
    config=Config(s3={'addressing_style': 'path'}) # <-- Ajoute cette ligne impérativement
)



BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME")

# Au démarrage de l'API
try:
    s3_client.create_bucket(Bucket=BUCKET_NAME)
    print(f"Bucket '{BUCKET_NAME}' créé ou déjà existant.")
except Exception as e:
    print(f"Note: Le bucket existe peut-être déjà : {e}")

@app.get("/")
async def root():
    return {"message": "API EUFactForce opérationnelle"}

# 4. Route d'upload
@app.post("/upload/")
async def upload_file(
    file: UploadFile = File(...),
    metadata: str = Form(...)
):
    try:
        # Nettoyage du nom de fichier
        filename = file.filename
        json_filename = f"{os.path.splitext(filename)[0]}.json"

        # A. Upload du PDF sur S3
        file_content = await file.read()
        s3_client.put_object(
            Bucket=BUCKET_NAME,
            Key=filename,
            Body=file_content,
            ContentType="application/pdf"
        )

        # B. Upload des métadonnées (JSON) sur S3
        # On vérifie que c'est du JSON valide avant d'envoyer
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
    # Lancement sur le port 8001 comme demandé
    uvicorn.run(app, host="0.0.0.0", port=8001)
