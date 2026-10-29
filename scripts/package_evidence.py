"""Package only reviewable CI evidence, never installers or local databases."""
from __future__ import annotations
import argparse
from pathlib import Path
import zipfile


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--artifacts',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    permitted={'.png','.json','.xml','.txt','.md','.csv'}
    files=[path for path in args.artifacts.rglob('*') if path.is_file()
           and path.suffix.lower() in permitted
           and not any(part.startswith('.') for part in path.relative_to(args.artifacts).parts)]
    if args.output.exists():
        raise FileExistsError('Refusing to replace evidence archive: '+str(args.output))
    with zipfile.ZipFile(args.output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            archive.write(path,path.relative_to(args.artifacts).as_posix())
    print(f'Packaged {len(files)} actual evidence files: {args.output}')


if __name__=='__main__':
    main()
