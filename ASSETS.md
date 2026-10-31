# Asset provenance

The MIT license in [LICENSE](LICENSE) covers the **code** in this repository
(`src/`, `tests/`, presets, the prompt template and CI configuration). It does
not cover the images.

## `examples/*.webp`

- The nine agent avatars used by TWO, all AI-generated for TWO and approved by TWO.
- The first seven were made with an image-generation model before this tool
  existed. They are stored byte-for-byte as approved (1254x1254, transparent WebP).
- `security-engineer-gunmetal.webp` and `ux-designer-lilac.webp` were generated
  with this tool (`gpt-image-2.5`, from the `security-engineer` and `ux-designer`
  presets). The approved 512x512 PNGs are stored as lossless WebP, pixel for pixel.
- `manifest.json` records each file's SHA-256 and the CI checks it.
- The `recipe` for each example in `manifest.json` is the preset and prompt this
  tool uses to generate a *new* variant in the same style. It is not a record of
  the exact prompt that produced the original, and generation is
  non-deterministic.
- They are included as style references and as a gallery. No further license is
  granted over them here, and no claim is made about rights in any third-party
  material that may have influenced the model or the style.

## Generated images

Images you generate with this tool come from the image API you call with your
own key. Their terms of use are set by that provider's terms, not by this
repository. This project is not affiliated with or endorsed by OpenAI or any
other model provider.
