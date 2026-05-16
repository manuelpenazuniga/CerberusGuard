# Local Setup for External Primitives

This repository integrates three external security primitives under `external/`.

## 1) Lobster Trap (Veea)

Clone:

```bash
git clone https://github.com/veeainc/lobstertrap.git external/lobstertrap
```

Build:

```bash
cd external/lobstertrap
make build
```

Binary:

```text
external/lobstertrap/lobstertrap
```

Smoke test:

```bash
./external/lobstertrap/lobstertrap --help
```

## 2) PennyPrompt

Clone:

```bash
git clone https://github.com/manuelpenazuniga/PennyPrompt.git external/pennyprompt
```

Build:

```bash
cd external/pennyprompt
cargo build --release
```

Binary:

```text
external/pennyprompt/target/release/penny-cli
```

Smoke test:

```bash
./external/pennyprompt/target/release/penny-cli --help
```

## 3) ClawCrate

Clone:

```bash
git clone https://github.com/manuelpenazuniga/ClawCrate.git external/clawcrate
```

Build:

```bash
cd external/clawcrate
cargo build --workspace --release
```

Binary:

```text
external/clawcrate/target/release/clawcrate
```

Smoke test:

```bash
./external/clawcrate/target/release/clawcrate --help
```
