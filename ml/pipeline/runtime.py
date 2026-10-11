"""Export authenticated runtime artifacts without training data."""
import argparse
import shutil
from pathlib import Path
from ml.pipeline.bundle import PipelineBundle, RUNTIME_ARTIFACTS


def export_runtime(source, destination):
    source, destination = Path(source), Path(destination)
    PipelineBundle.load_from_processed_dir(source, mode='STRICT_FITTED')
    destination.mkdir(parents=True, exist_ok=False)
    for name in ('release_manifest.json', *RUNTIME_ARTIFACTS):
        shutil.copyfile(source / name, destination / name)
    PipelineBundle.load_from_processed_dir(destination, mode='STRICT_FITTED')
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['export'])
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args()
    print(export_runtime(args.source, args.destination))


if __name__ == '__main__':
    main()
