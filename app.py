from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from PyPDF2 import PdfReader, PdfWriter
import os
from typing import Optional
import uuid
# apple 
# FastAPI app initialization
app = FastAPI()

# Database setup
DATABASE_URL = "postgresql://pw_database_user:9VOzTTM6Vs5djsapSx7zCgQfbxpbuJaq@dpg-cu7kp7qn91rc73d3rc80-a.oregon-postgres.render.com/pw_database"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Directory to temporarily save generated PDFs
GENERATED_PDFS_DIR = "generated_pdfs"
os.makedirs(GENERATED_PDFS_DIR, exist_ok=True)

# Database model
class PDFFile(Base):
    __tablename__ = "pdf_files"
    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(String, unique=True, index=True)
    file_name = Column(String)
    file_path = Column(String)

# Create the table
Base.metadata.create_all(bind=engine)

# Dependency to get the database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/customize-pdf/")
async def customize_pdf(
    pdf_file: UploadFile = File(...),
    orientation: Optional[str] = Form("portrait"),
    copies: Optional[int] = Form(1),
):
    """
    API to accept a PDF, customize it (rotate and duplicate), save it to the database, and return its ID.
    """
    # Save the uploaded PDF
    input_pdf_path = os.path.join(GENERATED_PDFS_DIR, pdf_file.filename)
    with open(input_pdf_path, "wb") as f:
        f.write(await pdf_file.read())

    # Generate customized PDF
    try:
        output_pdf_path = generate_pdf_with_customization(input_pdf_path, orientation, copies)

        # Generate a unique file ID
        file_id = str(uuid.uuid4())

        # Save the PDF details to the database
        db = next(get_db())
        new_pdf = PDFFile(
            file_id=file_id,
            file_name=os.path.basename(output_pdf_path),
            file_path=output_pdf_path,
        )
        db.add(new_pdf)
        db.commit()
        db.refresh(new_pdf)

        return {"status": "success", "file_id": file_id, "message": "PDF has been customized and saved."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get-pdf/{file_id}")
def get_pdf(file_id: str):
    """
    API to retrieve a PDF from the database using its unique ID.
    """
    db = next(get_db())
    pdf_file = db.query(PDFFile).filter(PDFFile.file_id == file_id).first()

    if not pdf_file:
        raise HTTPException(status_code=404, detail="PDF not found")

    # Return the file as a response
    return FileResponse(
        pdf_file.file_path,
        media_type="application/pdf",
        filename=pdf_file.file_name,
    )


def generate_pdf_with_customization(input_pdf_path: str, orientation: str, copies: int) -> str:
    """
    Generates a customized PDF based on the specified orientation and copies.
    """
    output_filename = f"customized_{os.path.basename(input_pdf_path)}"
    output_path = os.path.join(GENERATED_PDFS_DIR, output_filename)

    # Remove the file if it already exists
    if os.path.exists(output_path):
        os.remove(output_path)

    # Read the original PDF
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()

    for _ in range(copies):  # Add pages multiple times for the specified number of copies
        for page in reader.pages:
            if orientation == "landscape":
                page.rotate(90)  # Rotate page to landscape
            writer.add_page(page)

    # Write the customized PDF to the output path
    with open(output_path, "wb") as output_pdf:
        writer.write(output_pdf)

    return output_path


if __name__ == "__main__":
    import uvicorn
    import os



    # Use the port provided by Render, or default to 8000 for local testing
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on host 0.0.0.0 and port {port}")
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=False)

@app.get("/")
def home():
    return {"message": "Welcome to the FastAPI PDF Service!"}

