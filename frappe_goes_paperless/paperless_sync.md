
# Paperless Consumption Process

Ref: https://paperless.readthedocs.io/en/latest/consumption.html#hooking-into-the-consumption-process

### Paperless automatic sync script
`/usr/local/sbin/sync_docs.sh`

```bash
#!/bin/sh

DOCUMENT_ID=${DOCUMENT_ID:-$1}

FRAPPE_URL="https://erp.example.com"
API_KEY="xxxxxxxxxxxxx"
API_SECRET="xxxxxxxxxxx"

curl -sS -f --max-time 60 -o /dev/null \
    "${FRAPPE_URL}/api/method/frappe_goes_paperless.frappe_goes_paperless.tools.sync_documents" \
    -H "Authorization: token ${API_KEY}:${API_SECRET}" \
    -H "Content-Type: application/json" \
    -d "{\"paperless_document\": ${DOCUMENT_ID}}" \
    || echo "Frappe sync failed for Paperless document ${DOCUMENT_ID}" >&2
exit 0
```

- The API user needs the role `DMS Manager` (or `System Manager`).
- Without the `Content-Type` header Frappe does not read the JSON body and the call
  falls back to a full sync.
- If the ERP host name does not resolve inside the container, add
  `--resolve erp.example.com:443:<ip>` instead of switching to plain HTTP.
- The script contains credentials: `chown root:1000` and `chmod 750` (1000 = paperless
  user in the container). Edit it in place (e.g. `cat > sync_docs.sh`), a new file
  with a new inode is not visible through the existing bind mount until the container
  is recreated.
- Imports are serialized with a file lock and skip documents that already exist, so
  the hook and the manual sync button can run at the same time.

### Docker compose configuration

Add this line on the `docker-compose.yaml` file on the `webserver` container configuration volume:
```
- /usr/local/sbin/sync_docs.sh:/usr/local/sbin/sync_docs.sh:ro
```

Add this line on the `docker-compose.env` file at end:
```
PAPERLESS_POST_CONSUME_SCRIPT='/usr/local/sbin/sync_docs.sh'
```

