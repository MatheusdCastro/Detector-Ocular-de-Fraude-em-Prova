# Detector-Ocular-de-Fraude-em-Prova
Projeto final da disciplina de PDI. Sistema de Rastreamento Ocular para Detecção de Fraude em Provas

## Executar com o supervisor

Com o ambiente virtual ativo e as dependências de `requirements.txt` instaladas,
abra dois terminais na pasta do projeto.

1. No primeiro terminal, execute `python supervisor.py` e clique em **Iniciar servidor**.
2. No segundo terminal, execute `python app.py`. Clique em **Conectar** e em **Ligar câmera**.
3. A janela do supervisor exibe o vídeo. A aba **Notificações** mostra a direção
   atual e as últimas 100 mudanças com horário.

As duas janelas rodam no mesmo computador. O supervisor atende um usuário por
vez em `ws://127.0.0.1:8765`. A câmera local funciona sem o supervisor e pode
ser ligada antes de conectar. Se a conexão falhar, verifique se o servidor foi
iniciado e clique em **Conectar** novamente.
