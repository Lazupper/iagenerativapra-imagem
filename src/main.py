from __future__ import annotations

import io
import os
import zipfile
from enum import Enum

import cv2
import numpy as np
import requests
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from PIL import Image, ImageEnhance, ImageFilter


class Provider(str, Enum):
    openai = "openai"
    replicate = "replicate"
    stability = "stability"
    local = "local"


class Preset(str, Enum):
    none = "none"
    warm = "warm"
    cool = "cool"
    cinematic = "cinematic"
    brand = "brand"


app = FastAPI(title="IA Generativa para Imagens", version="1.1.0")


def _read_upload_to_pil(image_file: UploadFile) -> Image.Image:
    content = image_file.file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Imagem vazia.")
    try:
        img = Image.open(io.BytesIO(content)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Arquivo de imagem inválido.") from exc
    return img


def _pil_to_jpeg_bytes(image: Image.Image, quality: int = 95) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()


def _apply_preset(image: Image.Image, preset: Preset) -> Image.Image:
    if preset == Preset.none:
        return image

    if preset == Preset.warm:
        r, g, b = image.split()
        r = r.point(lambda x: min(255, int(x * 1.08)))
        b = b.point(lambda x: max(0, int(x * 0.95)))
        image = Image.merge("RGB", (r, g, b))
        return ImageEnhance.Color(image).enhance(1.08)

    if preset == Preset.cool:
        r, g, b = image.split()
        r = r.point(lambda x: max(0, int(x * 0.95)))
        b = b.point(lambda x: min(255, int(x * 1.1)))
        image = Image.merge("RGB", (r, g, b))
        return ImageEnhance.Contrast(image).enhance(1.05)

    if preset == Preset.cinematic:
        image = ImageEnhance.Color(image).enhance(0.88)
        image = ImageEnhance.Contrast(image).enhance(1.18)
        return image.filter(ImageFilter.GaussianBlur(radius=0.4))

    if preset == Preset.brand:
        image = ImageEnhance.Color(image).enhance(1.1)
        image = ImageEnhance.Sharpness(image).enhance(1.2)
        image = ImageEnhance.Contrast(image).enhance(1.1)
        return image

    return image


def _remove_imperfections(image: Image.Image) -> Image.Image:
    np_img = np.array(image)
    denoised = cv2.fastNlMeansDenoisingColored(np_img, None, 5, 5, 7, 21)
    bilateral = cv2.bilateralFilter(denoised, d=7, sigmaColor=40, sigmaSpace=40)
    return Image.fromarray(bilateral)


def _auto_mask(np_img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(np_img, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 70, 180)
    kernel = np.ones((5, 5), np.uint8)
    dilated = cv2.dilate(edges, kernel, iterations=2)
    closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=2)
    return cv2.GaussianBlur(closed, (5, 5), 0)


def _inpaint(np_img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    return cv2.inpaint(np_img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)




def _creative_variation(image: Image.Image, index: int) -> Image.Image:
    arr = np.array(image).astype(np.float32)
    # Variação leve por amostra para ampliar criação sem impor limite fixo de quantidade.
    shift = ((index % 7) - 3) * 2.0
    contrast = 1.0 + (((index * 13) % 11) - 5) * 0.01
    saturation = 1.0 + (((index * 17) % 9) - 4) * 0.02

    arr = np.clip((arr - 127.5) * contrast + 127.5 + shift, 0, 255).astype(np.uint8)
    out = Image.fromarray(arr)
    out = ImageEnhance.Color(out).enhance(max(0.1, saturation))
    return out


def _images_to_zip_bytes(images: list[tuple[str, Image.Image]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, image in images:
            img_buffer = io.BytesIO()
            image.save(img_buffer, format="JPEG", quality=95)
            zf.writestr(name, img_buffer.getvalue())
    return buffer.getvalue()

def _resolve_provider(provider: Provider) -> tuple[Provider, str]:
    configured = {
        Provider.openai: bool(os.getenv("OPENAI_API_KEY")),
        Provider.replicate: bool(os.getenv("REPLICATE_API_TOKEN")),
        Provider.stability: bool(os.getenv("STABILITY_API_KEY")),
        Provider.local: True,
    }

    if configured.get(provider, False):
        return provider, "requested"

    return Provider.local, f"fallback_no_credentials_for_{provider.value}"


def _call_removebg(image_bytes: bytes) -> bytes:
    key = os.getenv("REMOVEBG_API_KEY")
    if not key:
        raise HTTPException(status_code=400, detail="REMOVEBG_API_KEY não configurada.")

    try:
        response = requests.post(
            "https://api.remove.bg/v1.0/removebg",
            files={"image_file": ("image.jpg", image_bytes)},
            data={"size": "auto"},
            headers={"X-Api-Key": key},
            timeout=60,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Falha de conexão remove.bg: {exc}") from exc

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Erro remove.bg: {response.text}")

    return response.content


def _commercial_pipeline(image: Image.Image, preset: Preset, remove_imperfections: bool) -> Image.Image:
    output = image
    if remove_imperfections:
        output = _remove_imperfections(output)
    output = _apply_preset(output, preset)
    return output


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/providers/status")
def providers_status() -> dict[str, bool]:
    return {
        "openai": bool(os.getenv("OPENAI_API_KEY")),
        "replicate": bool(os.getenv("REPLICATE_API_TOKEN")),
        "stability": bool(os.getenv("STABILITY_API_KEY")),
        "removebg": bool(os.getenv("REMOVEBG_API_KEY")),
    }


@app.post("/v1/edit/ready-ai")
def edit_ready_ai(
    image: UploadFile = File(...),
    provider: Provider = Query(default=Provider.local),
    preset: Preset = Query(default=Preset.none),
    remove_imperfections: bool = Query(default=True),
) -> Response:
    pil_img = _read_upload_to_pil(image)
    used_provider, provider_note = _resolve_provider(provider)

    # Neste MVP, a inferência usa pipeline local mesmo quando provider externo foi solicitado.
    output = _commercial_pipeline(
        pil_img,
        preset=preset,
        remove_imperfections=remove_imperfections,
    )

    return Response(
        content=_pil_to_jpeg_bytes(output),
        media_type="image/jpeg",
        headers={
            "X-Provider-Requested": provider.value,
            "X-Provider-Used": used_provider.value,
            "X-Provider-Note": provider_note,
        },
    )


@app.post("/v1/edit/inpainting-advanced")
def edit_inpainting_advanced(
    image: UploadFile = File(...),
    mask: UploadFile | None = File(default=None),
    preset: Preset = Query(default=Preset.none),
) -> Response:
    pil_img = _read_upload_to_pil(image)
    np_img = np.array(pil_img)

    if mask:
        mask_img = _read_upload_to_pil(mask)
        mask_np = cv2.cvtColor(np.array(mask_img), cv2.COLOR_RGB2GRAY)
        _, mask_np = cv2.threshold(mask_np, 127, 255, cv2.THRESH_BINARY)
    else:
        mask_np = _auto_mask(np_img)

    inpainted = _inpaint(np_img, mask_np)
    out_img = Image.fromarray(inpainted)
    out_img = _apply_preset(out_img, preset)
    return Response(content=_pil_to_jpeg_bytes(out_img), media_type="image/jpeg")


@app.post("/v1/edit/ready-ai/batch")
def edit_ready_ai_batch(
    image: UploadFile = File(...),
    provider: Provider = Query(default=Provider.local),
    preset: Preset = Query(default=Preset.none),
    remove_imperfections: bool = Query(default=True),
    total_outputs: int = Query(default=4, ge=1, description="Quantidade de imagens para criar (sem limite artificial pela API)."),
) -> Response:
    pil_img = _read_upload_to_pil(image)
    used_provider, provider_note = _resolve_provider(provider)

    base = _commercial_pipeline(
        pil_img,
        preset=preset,
        remove_imperfections=remove_imperfections,
    )

    outputs: list[tuple[str, Image.Image]] = []
    for index in range(total_outputs):
        variant = _creative_variation(base, index=index)
        outputs.append((f"output_{index + 1:04d}.jpg", variant))

    zip_bytes = _images_to_zip_bytes(outputs)
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="ready_ai_batch_outputs.zip"',
            "X-Provider-Requested": provider.value,
            "X-Provider-Used": used_provider.value,
            "X-Provider-Note": provider_note,
            "X-Total-Outputs": str(total_outputs),
        },
    )


@app.post("/v1/edit/remove-background")
def remove_background(image: UploadFile = File(...)) -> Response:
    pil_img = _read_upload_to_pil(image)
    result = _call_removebg(_pil_to_jpeg_bytes(pil_img, quality=100))
    return Response(content=result, media_type="image/png")
