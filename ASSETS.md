# Asset provenance

The MIT license in [LICENSE](LICENSE) covers the **code** in this repository
(`src/`, `tests/`, presets, the prompt template and CI configuration). It does
not cover the images.

## `examples/*.webp`

- The seven agent avatars used by TWO. They were AI-generated for TWO with an
  image-generation model and approved by TWO before this tool existed.
- Each file is stored byte-for-byte as approved (1254x1254, transparent WebP).
  `manifest.json` records its SHA-256 and the CI checks it.
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
