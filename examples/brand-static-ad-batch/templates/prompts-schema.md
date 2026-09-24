# prompts.json schema

One object per template. Keep on-image copy short. Avoid straight double quotes inside strings, or write the file with a JSON serializer.

```json
{
  "brand": "element",
  "product": "<product name>",
  "aspect_ratio": "4:5",
  "resolution": "1K",
  "prompts": [
    {
      "id": 1,
      "slug": "headline",
      "concept": "Headline",
      "on_image_copy": "<short headline>",
      "prompt": "A single static ad image, not a grid. <scene>, the product from the reference images shown exactly as packaged, <brand colours hex>, <font style> headline reading: <copy>. <layout>. Clean, legible text.",
      "claims_source": "<URL or 'placeholder - human to replace'>"
    }
  ]
}
```

Before sending:
- Parse the file (for example `python -m json.tool prompts.json`).
- Every prompt asks for one single image.
- Every factual claim has a source or is marked as a placeholder.
