
````markdown
# 💳 Sistema de Geração de Boletos Bancários

Sistema em Python para geração automatizada de boletos bancários em PDF no padrão brasileiro, com interface gráfica (Tkinter), controle de parcelas e exportação de dados em JSON com integração ao GitHub.

---

🚀 Funcionalidades

- 📄 Geração de boletos bancários em PDF (padrão brasileiro)
- 🧾 Recibo integrado ao boleto
- 💰 Sistema de parcelas automáticas
- 🖥️ Interface gráfica intuitiva (Tkinter)
- 📁 Organização automática por ano/mês
- 📊 Exportação de dados em JSON
- ☁️ Integração com GitHub (backup de dados)
- 🔢 Controle de ID sequencial de boletos
- 🧮 Linha digitável e nosso número gerados automaticamente

---

🛠️ Tecnologias utilizadas

- Python 3
- Tkinter (interface gráfica)
- ReportLab (geração de PDF)
- Requests (integração com GitHub API)
- JSON (armazenamento de dados)
- Base64 (codificação de upload)

---

📦 Instalação

Clone o repositório:

```bash
git clone https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
cd SEU_REPOSITORIO
````

Instale as dependências:

```bash
pip install reportlab requests
```

---

▶️ Como executar

Execute o sistema com:

```bash
python main.py
```

---

🖥️ Como usar

1. Preencha os dados do pagador na interface
2. Defina número de parcelas e valor
3. Informe a data da primeira parcela
4. Clique em **"GERAR CREDIÁRIOS"**
5. Os PDFs serão gerados automaticamente na pasta:

```
Boletos_Gerados/
```

---

📁 Estrutura do projeto

```
📦 projeto
 ┣ 📂 Boletos_Gerados
 ┣ 📜 main.py
 ┣ 📜 boletos.json
 ┣ 📜 README.md
```

---

☁️ Integração com GitHub

O sistema realiza backup automático dos dados dos boletos no repositório GitHub configurado no código.

⚠️ **Importante:** Nunca exponha seu token diretamente no código. Utilize variáveis de ambiente.

---

🔐 Segurança

Recomendações:

* Não versionar tokens de acesso
* Utilizar variáveis de ambiente (`os.getenv`)
* Evitar expor dados sensíveis no repositório

---

📌 Status do Projeto

✔️ Funcional
✔️ Em uso interno
🔄 Em evolução contínua

---

👨‍💻 Autor

Desenvolvido para automação de geração de boletos e gestão de crediários.

