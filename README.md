# blackremove

FastAPI application to remove black backgrounds from logo images and output a transparent WebP.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the API:
   ```bash
   uvicorn main:app --reload
   ```

3. Call the API (via cURL):
   ```bash
   curl -X POST "http://localhost:8000/remove-bg" \
        -H "accept: application/json" \
        -H "Content-Type: multipart/form-data" \
        -F "file=@your_image.png" \
        -F "threshold=30" \
        -F "quality=95" \
        -F "feather=true" \
        --output result.webp
   ```
