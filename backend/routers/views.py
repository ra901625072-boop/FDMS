import os
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["views"])

# Setup Jinja2 templates directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
frontend_path = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))
templates = Jinja2Templates(directory=frontend_path)

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the landing page index.html"""
    if not os.path.exists(os.path.join(frontend_path, "index.html")):
        raise HTTPException(status_code=404, detail="Page not found")
    return templates.TemplateResponse(request=request, name="index.html", context={"active_page": "index"})

@router.get("/{page_name}.html", response_class=HTMLResponse)
async def read_page(request: Request, page_name: str):
    """Serve individual pages via Jinja2"""
    # Prevent directory traversal attacks
    if ".." in page_name or "/" in page_name or "\\" in page_name:
        raise HTTPException(status_code=400, detail="Invalid page request")
        
    template_file = f"{page_name}.html"
    template_path = os.path.join(frontend_path, template_file)
    
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Page not found")
        
    return templates.TemplateResponse(request=request, name=template_file, context={"active_page": page_name})
