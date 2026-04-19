# edds2png.py

I had maintained the original .NET version, ignore those files unless you would like to utilize the .net version.



Convert Bohemia `.edds` texture files to `.png`.

## Setup
First head into root folder and execute in your shell;
```sh
python -m pip install -r requirements.txt
```

For an editable command-line install:

```sh
python -m pip install -e .
```

## Usage

Run the package directly from the folder edds2png:

```sh
python -m edds2png path\to\texture.edds
```

Or pass a directory to convert every top-level `.edds` file in that directory:

```sh
python -m edds2png path\to\textures
```

If installed with `pip install -e .`, use the console command:

```sh
edds2png path\to\textures
```

Output PNG files are written beside the input files with the same base name.
