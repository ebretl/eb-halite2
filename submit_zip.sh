#!/bin/bash
chmod 0666 MyBot.py
chmod +x MyBot.py
zip -r submit.zip MyBot.py hlt/*.py
hlt_client/client.py bot -b submit.zip
