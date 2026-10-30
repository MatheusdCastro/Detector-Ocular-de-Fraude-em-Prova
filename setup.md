# Setup do ambiente de desenvolvimento (PI4 / PDI)

Este projeto usa o **[Pixi](https://pixi.sh)** para garantir que todo mundo da equipe tenha exatamente as mesmas versões de Python, CMake, Ninja, g++ e CUDA.

| Ferramenta | Versão |
|------------|--------|
| Python     | 3.14.x |
| CMake      | 4.2.x  |
| Ninja      | 1.13.x |
| g++        | 15.x (C++17) |
| CUDA (nvcc)| 13.1   |

---

## Pré-requisitos

- Linux x86_64 (Ubuntu recomendado)
- `git` e `curl` instalados

## 1. Instalar o Pixi (uma única vez por máquina)

A instalação é **por usuário**: não precisa de `sudo` e não mexe no sistema. Ele é instalado em `~/.pixi/bin`.

```bash
curl -fsSL https://pixi.sh/install.sh | bash
```

Feche e abra o terminal (ou rode `source ~/.bashrc`) e confirme:

```bash
pixi --version
```

---

## 2. Clonar o repositório

```bash
git clone https://github.com/MatheusdCastro/Detector-Ocular-de-Fraude-em-Prova.git
cd Detector-Ocular-de-Fraude-em-Prova
```

---

## 3. Instalar o ambiente do projeto

Dentro da pasta do projeto:

```bash
pixi install --locked
```

O `--locked` obriga o Pixi a usar exatamente as versões do `pixi.lock`, sem resolver nada de novo. Na primeira vez pode demorar (baixa compilador, CUDA toolkit etc.).

---

## 4. Usar o ambiente

**Opção A: entrar em um shell com tudo ativado**

```bash
pixi shell
```

Dentro dele, confira:

```bash
python --version
cmake --version
ninja --version
g++ --version
nvcc --version
```

Para sair: `exit`.

**Opção B: rodar um comando avulso sem entrar no shell**

```bash
pixi run python script.py
pixi run cmake --version
```

**Opção C: usar as tasks do projeto** (definidas no `pixi.toml`)

```bash
pixi run configure   # cmake -S . -B build -G Ninja
pixi run build       # cmake --build build
```

---

## 5. Compilando

Padrão do projeto: **C++17** (já fixado no `CMakeLists.txt`).

```bash
pixi run configure
pixi run build
```

Se compilar manualmente com g++:

```bash
pixi run g++ -std=c++17 main.cpp -o main
```

---

## 6. Adicionando dependências (regras da equipe)

Nunca use `pip install` ou `conda install` direto. Use sempre o Pixi, para o `pixi.toml` e o `pixi.lock` ficarem atualizados:

```bash
pixi add numpy opencv          # pacotes do conda-forge
pixi add --pypi nome-do-pacote # pacotes só do PyPI
```

Depois **commite os dois arquivos**:

```bash
git add pixi.toml pixi.lock
git commit -m "chore: adiciona <pacote>"
git push
```

Quando alguém puxar a mudança (`git pull`), basta rodar `pixi install --locked` de novo.

---

## Problemas comuns

**`pixi: command not found`**
Reabra o terminal ou rode `source ~/.bashrc`. Confira se `~/.pixi/bin` está no `PATH`.

**`nvcc` funciona mas o programa não roda na GPU**
Driver desatualizado. Veja `nvidia-smi` e atualize o driver.

**Erro de host compiler no nvcc (g++ não suportado)**
Force o compilador no CMake:

```bash
pixi run cmake -S . -B build -G Ninja -DCMAKE_CUDA_HOST_COMPILER=$(pixi run which g++)
```

**Ambiente corrompido ou estranho**
Apague e recrie (não perde nada, o lock garante as mesmas versões):

```bash
rm -rf .pixi
pixi install --locked
```