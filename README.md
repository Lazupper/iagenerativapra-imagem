# IA Generativa para Edição de Imagens

Este projeto entrega uma **IA generativa prática para edição de imagens** com dois modos:

1. **IA pronta (rápido/comercial)** usando APIs de mercado com identidade visual própria.
2. **Inpainting avançado** para remover objetos e reconstruir áreas automaticamente.

## Funcionalidades

- Detecção de áreas com OpenCV
- Máscara automática (heurística local)
- Inpainting para remover objetos/imperfeições
- Ajuste de cor por presets (warm, cool, cinematic, brand)
- Pipeline comercial com seleção de provider e fallback local
- Geração em lote (`batch`) para criar múltiplas versões sem limite artificial de quantidade
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


### 2) IA pronta/comercial em lote (sem limite artificial)

`POST /v1/edit/ready-ai/batch`

- `image`: arquivo de imagem
- `provider`: `openai | replicate | stability | local`
- `preset`: `none | warm | cool | cinematic | brand`
- `remove_imperfections`: `true/false`
- `total_outputs`: número de variações que deseja gerar (`>=1`)

Retorna um arquivo `.zip` com todas as imagens criadas.

Exemplo:

```bash
curl -X POST "http://localhost:8000/v1/edit/ready-ai/batch?provider=local&preset=brand&total_outputs=20" \
  -F "image=@./exemplo.jpg" \
  --output lote_ready_ai.zip
```

### 3) Inpainting avançado

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

### 4) Status dos providers

`GET /v1/providers/status`

Retorna quais integrações têm credenciais configuradas no ambiente.

### 5) Remoção de fundo (remove.bg)

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

> Observação: neste MVP a transformação de imagem é local. Nos endpoints `ready-ai`, os headers `X-Provider-*` indicam provider solicitado, provider usado e motivo de fallback.
>
> `total_outputs` no endpoint batch não possui teto artificial na API; o limite prático depende dos recursos da máquina (CPU/RAM/tempo).

## Observações

- O projeto foi desenhado para ser base de produto: você pode plugar seu próprio prompt, LUT, assinatura visual e regras de pós-processamento.
- Para máscaras automáticas mais robustas, o próximo passo é integrar SAM (Segment Anything Model).
