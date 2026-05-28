# Sistema SaaS para Estética Automotiva

## Como rodar localmente

1. Extraia o ZIP.
2. Abra a pasta `SISTEMA ESTETICA` no VS Code.
3. No terminal, rode:

```bash
python -m venv venv
```

No Windows:

```bash
venv\Scripts\activate
```

Depois instale as dependências:

```bash
pip install -r requirements.txt
```

E execute:

```bash
python app.py
```

Acesse no navegador:

```text
http://127.0.0.1:5000
```

## Login inicial

Usuário: `admin`  
Senha: `admin123`

Altere o usuário e a senha em **Configurações**.

## O que foi melhorado nesta versão

- Nome do sistema editável nas configurações.
- Nome da empresa editável.
- Upload de logo.
- Cor principal personalizável.
- Tema claro/escuro.
- Identidade visual refletindo no menu, login, dashboard, relatórios e PDFs.
- Dashboard mais organizado para tarefas, serviços do dia, orçamentos pendentes e retornos.
- Melhorias visuais em botões, cards, formulários, responsividade e feedback visual.
- Banco preparado para migração automática sem apagar dados existentes.

## Publicação em servidor

Para Render/Railway/VPS, use preferencialmente:

```bash
gunicorn app:app
```

O banco é inicializado automaticamente ao carregar a aplicação.

## Ajuste visual claro
Esta versão usa um tema claro moderno por padrão, com fundo cinza/azulado suave, cards claros e cor principal azul. A cor principal, logo, nome do sistema, nome da empresa e tema podem ser alterados em Configurações.
