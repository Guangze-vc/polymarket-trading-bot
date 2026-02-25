import os
import dotenv
from py_builder_relayer_client.client import RelayClient
from py_builder_signing_sdk.config import BuilderConfig
from py_builder_signing_sdk.sdk_types import BuilderApiKeyCreds
from py_clob_client.client import ClobClient
from poly_web3 import RELAYER_URL, PolyWeb3Service

dotenv.load_dotenv()

def run_redeem_all() -> tuple[bool, str]:
    try:
        host = os.getenv("POLY_CLOB_HOST", "https://clob.polymarket.com")
        chain_id = int(os.getenv("POLY_CHAIN_ID", "137"))
        
        pk = os.getenv("POLY_PRIVATE_KEY") or os.getenv("POLY_API_KEY")
        if not pk:
            return False, "POLY_PRIVATE_KEY is missing from environment."
            
        funder = os.getenv("POLY_SAFE_ADDRESS") or os.getenv("POLYMARKET_PROXY_ADDRESS")
        if not funder:
            return False, "POLY_SAFE_ADDRESS is missing from environment."
            
        sig_type = int(os.getenv("POLY_SIGNATURE_TYPE", "2"))

        client = ClobClient(
            host,
            key=pk,
            chain_id=chain_id,
            signature_type=sig_type,
            funder=funder,
        )
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
        except Exception as e:
            return False, f"Failed to derive CLOB API creds: {e}"

        builder_key = os.getenv("POLY_BUILDER_API_KEY") or os.getenv("BUILDER_KEY")
        builder_secret = os.getenv("POLY_BUILDER_API_SECRET") or os.getenv("BUILDER_SECRET")
        builder_passphrase = os.getenv("POLY_BUILDER_API_PASSPHRASE") or os.getenv("BUILDER_PASSPHRASE")

        relayer_client = None
        if builder_key and builder_secret and builder_passphrase:
            relayer_client = RelayClient(
                RELAYER_URL,
                chain_id,
                pk,
                BuilderConfig(
                    local_builder_creds=BuilderApiKeyCreds(
                        key=builder_key,
                        secret=builder_secret,
                        passphrase=builder_passphrase,
                    )
                ),
            )
            
        rpc_url = os.getenv("POLY_RPC_URL", "https://polygon-bor.publicnode.com")

        service = PolyWeb3Service(
            clob_client=client,
            relayer_client=relayer_client,
            rpc_url=rpc_url,
        )

        redeem_list = service.redeem_all(batch_size=10)
        
        if redeem_list:
            return True, f"Redeemed {len(redeem_list)} batch(es). result: {redeem_list}"
        else:
            return True, "No redeemable positions found."
    except Exception as e:
        return False, f"Error in run_redeem_all: {str(e)}"

if __name__ == "__main__":
    success, msg = run_redeem_all()
    print("Success:", success)
    print("Message:", msg)
