# Host key for the SSH server used in tests.
# Do NOT use this key for any real server.
from paramiko import RSAKey
import io

def get_test_host_key() -> RSAKey:
    private_key_pem = """-----BEGIN RSA PRIVATE KEY-----
    MIIEpAIBAAKCAQEA2QvfQPkMLoSOFcD3+T7itSBHUGF/npApcOdC/D69GKmGAdYa
    pPT1s61yxaX2RIDPK+95BPD+TWXBSStjGuuY5PjHCFHbbwySwqKrOM4H6Ok7NDAs
    3TFnZUS9cZwDrcb+o1XnnzxW69kd/21Yqx+7wdegW16F1W0wUw8JBue6SEPpAYJI
    6NsdO1fF0M6ITGS34dlLo9EssWS0/hM++ZyfOK0B4mGLpn4nBKncB/bWhr++Qccz
    V3zA5Rf+JWl2yN8v07sB+uTZmWe/NgyC2+QuP11ci7qfWHMRFhCtOoY6nDn9EkKV
    mcvZEPzOAmlNDU3Jg7eUnPknrd8755YirZlrgwIDAQABAoIBABRWEO55B0OqhteR
    84oGct5urk/hOsBkGIXsHTIePMB9TcGJSojPLOBPbZQIR0lG2mJu9yNX4zPkR1Zw
    OsJwdaxqhNeKN+mxP2T+MdXKNCKGC9aJdwKomNv7s1ZcPFoBbaVnLKMWV7yUZMOk
    fqzV9dUlO3CkLB0BtIfrvjhH6QPRMNQmMv1wNGi/Ho7PCwx+6kOxECxl0wRdvFVq
    Q6ZzYYRtpLyOdA+EHHPJ2b0lRRHPsdVUcEoaDoq3BLfv3sglxsOvei/oRuVyV4VF
    XhxJvDhKqZ80Y6B0WOlLtCBmof5ko7DLU8TuiRnqYCTB8FWGq50ZZOYSAX/hkPl2
    xW3hoH0CgYEA++0LUVVTsicV+xN9z73Ao4RCx23ehuuYmfmnJLk7WdQeuIeuS+wD
    43JkswCkSUvvOzkG+dqV2xeE/6RTyVSwN4/KLmbTPPCnjaqrAMEcqxvdyQLrD4o1
    gY5WZALn3NpECDNPH7eFXYZKTBoZuY4u43I5Kfsznzt78eO7/TAZIFUCgYEA3I5t
    yhYYYdjDemezKG6Kcy+cUSmWM93SPx1pXn1fKsK09+dbEZ6/DfDaY9VF077mSgAs
    EpwibPO36e6PXN2TDSIOo/Ov8IKYFrZDnwKq+Y8l3LTl34YzVM2jQVqwtuQEK2JG
    a/i71viNcTR0d+YjNTTTfGS9po1RLj9642eR1HcCgYBoPwOy6TsT+kaHOd6SyzNe
    toknmxg8/lqMRJlcgeXEWxlHRKXkNsq5IIn45GgXCHv7JrLzSvc9zPK1Elu1cPzm
    UPLZ1qTMj8zVu2y9iCuDxqk016dLK+bOMIchJW6qngsO1aSFPFzMgZhW+2nvtZ1D
    cu2iqJcI6gV058bPk0qibQKBgQCWsq6rdNtmB8DQ4wgT6SuqNm69OggKGldsjoEP
    ceRTiEQ0Wpzr9iaetOHTcsbKPlaFW4bBlHMlNIWGTl0gW7j9MTcFqRye3exjIFgl
    zqHZ8IgzPFsQllZ+bB9PKVMzM6rxpa1uWr6lzKCAKBIoVlPaJ+UUypSWt1ovmmox
    9PM8UwKBgQDqn1s8bVZmtms+wzT0ciBj+wzkmj8PHUDuyWjn7g/A5CUwx36nqgPo
    /ZSEZpqkGA4WVGktymjlfVHMvDlnJbNuFJPkuwW0PiedEPlLpL1kD4UWtIYY8RKa
    lO/l7BuZYMyoLdz0v48+jAeEdZQyA5jaiQdd801WPT2MCPzPVRAMiQ==
    -----END RSA PRIVATE KEY-----"""
    return RSAKey.from_private_key(io.StringIO(private_key_pem))