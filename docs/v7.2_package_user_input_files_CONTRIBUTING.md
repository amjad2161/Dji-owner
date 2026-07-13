# Contributing

Thanks for considering a contribution! This project documents legal, manufacturer-supported workflows for DJI drone pilots. Contributions are welcome from pilots, content creators, developers, and translators.

## What we accept

- ✅ New walkthroughs for officially supported features
- ✅ Tool integrations using DJI Mobile SDK / Onboard SDK / Payload SDK
- ✅ Open-source community tools that operate within DJI's official SDKs
- ✅ Hebrew, Arabic, Spanish, French, and other language translations
- ✅ Per-country regulatory references and updates
- ✅ Mission templates (Litchi, DJI Pilot 2, Drone Harmony)
- ✅ Compatibility data corrections
- ✅ Bug reports and reproductions for tools in `tools/`

## What we will not accept

- ❌ Firmware patches, NFZ removal, or geofence bypass
- ❌ Tools that exceed legal transmit power
- ❌ Methods to bypass Remote ID or evade detection systems (Aeroscope etc.)
- ❌ Anything that could endanger people, aircraft, or property
- ❌ Cracked or pirated software references

If in doubt, open an issue first.

## How to contribute

1. Fork the repository.
2. Create a topic branch: `git checkout -b docs/your-topic` or `feat/your-feature`.
3. Keep documentation in `docs/en/` and `docs/he/` (translation pairs encouraged).
4. Keep tools in `tools/<tool-name>/` with their own README and license-compatible dependencies.
5. Open a pull request describing the change and the drone models / regions affected.

## Style

- Write for beginners. Assume zero programming experience unless the doc is in `tools/`.
- Cite sources for regulatory claims. Link to the authority page (FAA, EASA, CAAI, CAA, etc.), not blog posts.
- Test scripts on at least Windows 10 and Windows 11 before submitting.

## Code of conduct

Be respectful. Drone communities thrive when knowledge is shared without gatekeeping.
