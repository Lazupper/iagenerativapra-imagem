# IA Generativa para Edição de Imagens

Este projeto entrega uma **IA generativa prática para edição de imagens** com dois modos:

1. **IA pronta (rápido/comercial)** usando APIs de mercado com identidade visual própria.
2. **Inpainting avançado** para remover objetos e reconstruir áreas automaticamente.

## Funcionalidades

- Detecção de áreas com OpenCV
- Máscara automática (heurística local)
- Inpainting para remover objetos/imperfeições
- Ajuste de cor por presets (warm, cool, cinematic, brand)
- Pipeline com APIs externas (OpenAI/Replicate/Stability) com fallback local
- Endpoint para remoção de fundo via `remove.bg` (se chave estiver configurada)

## Stack

- Python 3.11+
- FastAPI
- OpenCV
- Pillow
- NumPy
- Requests

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Executar

```bash
uvicorn src.main:app --reload --port 8000
```

## Endpoints

### 1) IA pronta/comercial

`POST /v1/edit/ready-ai`

- `image`: arquivo de imagem
- `provider`: `openai | replicate | stability | local`
- `preset`: `none | warm | cool | cinematic | brand`
- `remove_imperfections`: `true/false`

Exemplo:

```bash
curl -X POST "http://localhost:8000/v1/edit/ready-ai?provider=local&preset=cinematic&remove_imperfections=true" \
  -F "image=@./exemplo.jpg" \
  --output resultado_ready.jpg
```

### 2) Inpainting avançado

`POST /v1/edit/inpainting-advanced`

- `image`: arquivo de imagem
- `mask`: máscara opcional (branco = remover)
- `preset`: `none | warm | cool | cinematic | brand`

Sem máscara enviada, o sistema cria máscara automática com OpenCV.

Exemplo:

```bash
curl -X POST "http://localhost:8000/v1/edit/inpainting-advanced?preset=brand" \
  -F "image=@./exemplo.jpg" \
  --output resultado_inpaint.jpg
```

### 3) Remoção de fundo (remove.bg)

`POST /v1/edit/remove-background`

- `image`: arquivo de imagem

Requer `REMOVEBG_API_KEY`.

## Variáveis de ambiente

```bash
export OPENAI_API_KEY="..."
export REPLICATE_API_TOKEN="..."
export STABILITY_API_KEY="..."
export REMOVEBG_API_KEY="..."
```

> Sem chave configurada, o modo `ready-ai` cai automaticamente para pipeline local.

## Observações

- O projeto foi desenhado para ser base de produto: você pode plugar seu próprio prompt, LUT, assinatura visual e regras de pós-processamento.
- Para máscaras automáticas mais robustas, o próximo passo é integrar SAM (Segment Anything Model).
