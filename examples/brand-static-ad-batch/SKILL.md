---
name: brand-static-ad-batch
description: "Use when someone asks to research a brand and batch-generate many static image ads (for example 40 ad concepts) from its real product photos with Nano Banana 2 through the fal API."
---

## When to use
The person wants a high volume of static ad creatives for one brand or product: DTC brands, agencies, performance teams. They have or can get product photos and a brand URL.

## What is new here
- Run three phases in order: brand DNA, then templated prompts, then image generation. Each phase leaves a file on disk.
- Nano Banana 2 on fal: `fal-ai/nano-banana-2/edit` takes the prompt plus product photos (`image_urls`), `num_images` 1-4, `aspect_ratio`, `resolution` 0.5K/1K/2K/4K, `output_format`. About $0.08 per image at 1K, so 40 ads cost about $3.20.
- Known failure points: .avif inputs, quotes inside prompts, several images per call, and the script only worked once the fal docs were supplied.

## Setup
1. Check what exists: `python --version`, `python -c "import fal_client"`, and whether `FAL_KEY` is set. Never print the key's value.
2. Ask before installing or signing up. If the person agrees: `pip install fal-client`, and create a key at https://fal.ai. The key goes in the `FAL_KEY` environment variable, never in a script or a committed file.
3. Project layout:
   - `brands/<brand>/product-images/`
   - `references/ad-templates.md` (the concept templates, with placeholders)
   - `generate_ads.py`
4. Verify: run one template at 1K and confirm the result contains `images[0].url`.
5. Other tools can generate too (for example Higgsfield's web UI, where the original framework was done by hand). fal is one option, chosen here for a clean API.

## Steps
1. **Collect inputs.** Ask for the brand URL, the exact product, 1 to 3 clean product-only photos, the aspect ratio (for example 4:5 or 1:1 for feeds, 9:16 for stories), and which templates to run. If Claude cannot download the photos, ask the person to save them into `product-images/`.
2. **Normalise images.** Convert .avif or .webp files to PNG before any upload. Keep the product clear and unobstructed.
3. **Phase 1: brand DNA.** Research the brand with web search and fill `templates/brand-dna.md`. Save the result as `brands/<brand>/brand-dna.md`. Cover the overview, visual system (hex colours, fonts), photography direction, packaging, product details, advertising tone, and real claims or reviews with their source URLs.
4. **Phase 2: prompts.** Read the templates and the brand DNA. Fill every placeholder with brand-specific details: colours, font style, product name, real benefits. Write `brands/<brand>/prompts.json` using the schema in `templates/prompts-schema.md`. Put the ad copy inside the prompt exactly as it should render. Escape or avoid straight double quotes inside prompt strings, or write the JSON with a proper serializer.
5. **Show the person 3 to 5 prompts** and the cost estimate (count x $0.08 at 1K) before generating.
6. **Phase 3 test.** Generate only about 5 templates, for example 1, 7, 9, 13, 15. For each one, upload the product images with `fal_client.upload_file`, then call `fal_client.subscribe("fal-ai/nano-banana-2/edit", arguments={prompt, image_urls, num_images: 1, aspect_ratio, resolution: "1K", output_format: "png"})`. Upload the product images once and reuse the URLs. Download each result into `brands/<brand>/output/<id>-<slug>/`.
7. **If the script errors**, get the current fal docs (the model's API page, or the LLM copy-all on the docs page) and fix the script against them. Do not guess parameter names.
8. **Review the test images** with the person: product fidelity, text spelling, text overflow, brand colours. Adjust the templates, not just single outputs.
9. **Full run** only after approval. Log failures per template and keep going. Retry failures individually.

## Pitfalls
- A prompt that describes a grid or several variants produces a collage. Ask for a single ad in the prompt and set `num_images` to 1.
- A quotation mark inside a prompt broke the pipeline. Validate `prompts.json` before sending anything.
- Long testimonial quotes can overflow their text area. Keep the on-image copy short.
- The model will invent reviews, offers, stats and celebrity logos if the template asks for them. Use only claims from the brand DNA sources, and mark any invented copy as a placeholder for a human to replace.
- A `skills/` folder in the project root is not a Claude Code skill. Real project skills live in `.claude/skills/<name>/SKILL.md`.

## Limits
- The 40 original concept templates are not public in the video. Use the person's own library, or write concepts together (headline, offer, testimonial, feature/benefits, bullet points, social proof, us vs them, negative marketing, stat-surrounded hero, and so on).
- AI ads still need human checks for legal claims, trademarks and platform ad policies before they run.
- Prices and parameters change. Recheck the fal model page before quoting costs.

---
Source: https://www.youtube.com/watch?v=tFyKaGP64M4, by Mike Futia | SCALE AI, 2026-03-13. Extracted with TAVIS on 2026-09-24 (Claude Code (your subscription); platform automatic captions (en-orig)).
Warnings at extraction: sponsored: The creator sells a playbook opt-in and a paid community that includes the finished project. The 40 templates and the script are not in the video; they sit behind links.; unverifiable: The creator says he had not tested the script before recording. The 'insane' results are shown briefly and chosen by him, and at least one had text overflow.; risky: He pasted the fal API key straight into the Python script. Use an environment variable so the key never lands in files or git.; risky: The generated ads showed invented testimonials, a 'free sample pack' offer and a celebrity podcast icon. Fake reviews, unapproved offers and third-party marks can break ad-platform rules and consumer law. A human must check every claim before it runs.; outdated: Model names, endpoint parameters and prices change fast. Checked on fal on 2026-09-24: $0.08 per image at 1K.; other: The video's 'skills' folder in the project root is just a folder of instructions, not a real Claude Code skill. Real project skills live in .claude/skills/<name>/SKILL.md.
