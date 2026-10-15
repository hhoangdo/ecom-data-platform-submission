path "*" { capabilities = ["create","read","update","delete","list","sudo"] }
path "sys/generate-root/*" { capabilities = ["deny"] }
path "sys/rekey/*" { capabilities = ["deny"] }
path "sys/seal" { capabilities = ["deny"] }
