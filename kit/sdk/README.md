# Sony's Camera Remote SDK goes here

1. Download Sony's Camera Remote SDK for your computer's system from Sony's
   [Camera Remote SDK page](https://support.d-imaging.sony.co.jp/app/sdk/l/index.php). It is free, by application
   to Sony, and you accept Sony's agreement when you download it. The file is named
   `CrSDK_v<version>_<date>_<system>.zip`, where the system is `Mac`, `Linux64PC`, `Linux64ARMv8` or `Win64`.
2. Put the zip, as it is, into this folder.
3. From the clone's root, run `python3 kit/setup.py` (on Windows, `py kit\setup.py`).

The setup command unpacks the zip here: its files, then `SimpleCli/` (the headers and the libraries the kit builds
against), `CrSDK_API_Reference_v<version>/` (read by `kit/tools/sdk_support.py`) and, on Windows, `Driver/` (the USB
driver). It checks the tools and says how to install any that are missing, makes `.venv`, builds the camera link
(`kit/link/`), the editor's camera helper (`kit/probe/`) and, on macOS, the OCR helper, and runs the kit's tests. On a
Linux system without `libxml2.so.2` it also builds that library in `.build/` here. `--check` only reports what is in
place.

Everything in this folder but this README is ignored by git and never leaves your computer: Sony's agreement does not
allow the SDK to be shared. The same steps by hand are in `docs/PORTING.md`, "Setup per OS".
