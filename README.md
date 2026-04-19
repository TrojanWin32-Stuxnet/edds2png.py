# edds2png

Convert Bohemia `.edds` texture files to `.png`.

## Setup

```powershell
python -m pip install -r requirements.txt
```

For an editable command-line install:

```powershell
python -m pip install -e .
```

## Usage

Run the package directly:

```powershell
python -m edds2png path\to\texture.edds
```

Or pass a directory to convert every top-level `.edds` file in that directory:

```powershell
python -m edds2png path\to\textures
```

If installed with `pip install -e .`, use the console command:

```powershell
edds2png path\to\textures
```

Output PNG files are written beside the input files with the same base name.
