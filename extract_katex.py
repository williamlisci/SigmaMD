import tarfile
from pathlib import Path

archive = Path("katex-0.19.0.tgz")
target = Path("assets/katex")
target.mkdir(parents=True, exist_ok=True)

with tarfile.open(archive, "r:gz") as tar:
    for member in tar.getmembers():
        if not member.isfile():
            continue

        if member.name == "package/LICENSE":
            relative = Path("LICENSE")
        elif member.name.startswith("package/dist/"):
            relative = Path(
                member.name.removeprefix("package/dist/")
            )
        else:
            continue

        destination = target / relative
        destination.parent.mkdir(
            parents=True, exist_ok=True
        )

        source = tar.extractfile(member)
        if source is not None:
            destination.write_bytes(source.read())

print("KaTeX assets extracted successfully.")
