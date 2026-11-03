# Asset provenance

The MIT license in [LICENSE](LICENSE) covers the **code** in this repository
(`src/`, `tests/`, presets, the prompt template and CI configuration). It does
not cover the images.

## `examples/*.webp`

- The twenty-three avatars used by TWO (fourteen agents, the Paperclip Operator
  board account and the eight council avatars), all AI-generated for TWO and approved by TWO.
- `security-engineer-gunmetal.webp`, `ux-designer-lilac.webp`,
  `applied-cryptography-reviewer-sky.webp`, `release-manager-navy.webp`,
  `ledger-writer-parchment.webp`, `reverse-engineer-rosegold.webp`,
  `agent-toolsmith-olive.webp` and
  `paperclip-operator-steel.webp` were generated with this tool (`gpt-image-2.5`,
  from the `security-engineer`, `ux-designer`, `applied-cryptography-reviewer`,
  `release-manager`, `ledger-writer`, `reverse-engineer`, `agent-toolsmith` and `paperclip-operator` presets). The approved 512x512 PNGs are stored as lossless WebP, pixel for pixel.
- The eight council avatars (`board-secretary-pearl.webp`,
  `seat-anthropic-terracotta.webp`, `seat-openai-lime.webp`,
  `seat-google-plum.webp`, `seat-meta-forest.webp`,
  `seat-moonshot-charcoal.webp`, `seat-xai-ruby.webp` and `seat-alt-2-aqua.webp`) were generated with
  this tool on 2026-11-02 (`gpt-image-2.5` through an OpenAI-compatible proxy,
  from the `board-secretary` and `seat-*` presets). The approved 512x512 PNGs are
  stored as lossless WebP, pixel for pixel. Emblems are generic symbols; none
  copies a company logo.
- The other seven were made with an image-generation model before this tool
  existed. They are stored byte-for-byte as approved (1254x1254, transparent WebP).
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
