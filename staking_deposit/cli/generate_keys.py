import os
import click
from typing import (
    Any,
    Callable,
)
from web3 import Web3

from eth_typing import HexAddress
from staking_deposit.credentials import (
    CredentialList
)
from staking_deposit.exceptions import ValidationError
from staking_deposit.utils.validation import (
    verify_deposit_data_json,
    validate_int_range,
    validate_password_strength,
    validate_eth1_withdrawal_address,
    validate_ether_amount_range
)
from staking_deposit.utils.constants import (
    ETH2GWEI,
    MAX_DEPOSIT_AMOUNT,
    DEFAULT_VALIDATOR_KEYS_FOLDER_NAME,
)
from staking_deposit.utils.ascii_art import EARTH_0
from staking_deposit.utils.click import (
    captive_prompt_callback,
    choice_prompt_func,
    jit_option,
)
from staking_deposit.utils.intl import (
    closest_match,
    load_text,
)
from staking_deposit.settings import (
    ALL_CHAINS,
    MAINNET,
    PRATER,
    get_chain_setting,
    ABI
)

w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth_goerli'))

def get_earth_node_address(validator_key: str) -> str:
    earth_staking_controller=w3.eth.contract(address='0x9a17f54D7c0300F5aD9D14B5aBEd877003CeF2c9', abi=ABI)
    earth_node_address=earth_staking_controller.functions.getEarthNodeAddress('0x'+validator_key).call()
    return earth_node_address

def get_password(text: str) -> str:
    return click.prompt(text, hide_input=True, show_default=False, type=str)

def generate_keys_arguments_decorator(function: Callable[..., Any]) -> Callable[..., Any]:
    '''
    This is a decorator that, when applied to a parent-command, implements the
    to obtain the necessary arguments for the generate_keys() subcommand.
    '''
    decorators = [
        jit_option(
            callback=captive_prompt_callback(
                lambda num: validate_int_range(num, 1, 2**32),
                lambda: load_text(['num_validators', 'prompt'], func='generate_keys_arguments_decorator')
            ),
            help=lambda: load_text(['num_validators', 'help'], func='generate_keys_arguments_decorator'),
            param_decls="--num_validators",
            prompt=lambda: load_text(['num_validators', 'prompt'], func='generate_keys_arguments_decorator'),
        ),
        jit_option(
            default=os.getcwd(),
            help=lambda: load_text(['folder', 'help'], func='generate_keys_arguments_decorator'),
            param_decls='--folder',
            type=click.Path(exists=True, file_okay=False, dir_okay=True),
        ),
        jit_option(
            callback=captive_prompt_callback(
                lambda x: closest_match(x, list(ALL_CHAINS.keys())),
                choice_prompt_func(
                    lambda: load_text(['chain', 'prompt'], func='generate_keys_arguments_decorator'),
                    list(ALL_CHAINS.keys())
                ),
            ),
            default=MAINNET,
            help=lambda: load_text(['chain', 'help'], func='generate_keys_arguments_decorator'),
            param_decls='--chain',
            prompt=choice_prompt_func(
                lambda: load_text(['chain', 'prompt'], func='generate_keys_arguments_decorator'),
                # Since `prater` is alias of `goerli`, do not show `prater` in the prompt message.
                list(key for key in ALL_CHAINS.keys() if key != PRATER)
            ),
        ),
        jit_option(
            callback=captive_prompt_callback(
                lambda num: validate_ether_amount_range(num),
                lambda: load_text(['num_validators', 'prompt'], func='generate_keys_arguments_decorator')
            ),
            default=MAX_DEPOSIT_AMOUNT // ETH2GWEI,
            help=lambda: load_text(['amount', 'help'], func='generate_keys_arguments_decorator'),
            param_decls="--amount",
        ),
        jit_option(
            callback=captive_prompt_callback(
                validate_password_strength,
                lambda:load_text(['keystore_password', 'prompt'], func='generate_keys_arguments_decorator'),
                lambda:load_text(['keystore_password', 'confirm'], func='generate_keys_arguments_decorator'),
                lambda: load_text(['keystore_password', 'mismatch'], func='generate_keys_arguments_decorator'),
                True,
            ),
            help=lambda: load_text(['keystore_password', 'help'], func='generate_keys_arguments_decorator'),
            hide_input=True,
            param_decls='--keystore_password',
            prompt=lambda: load_text(['keystore_password', 'prompt'], func='generate_keys_arguments_decorator'),
        ),
        jit_option(
            callback=captive_prompt_callback(
                lambda address: validate_eth1_withdrawal_address(None, None, address),
                lambda: load_text(['arg_execution_address', 'prompt'], func='generate_keys_arguments_decorator'),
                lambda: load_text(['arg_execution_address', 'confirm'], func='generate_keys_arguments_decorator'),
                lambda: load_text(['arg_execution_address', 'mismatch'], func='generate_keys_arguments_decorator'),
            ),
            default=None,
            help=lambda: load_text(['arg_execution_address', 'help'], func='generate_keys_arguments_decorator'),
            param_decls=['--execution_address', '--eth1_withdrawal_address'],
        ),
    ]
    for decorator in reversed(decorators):
        function = decorator(function)
    return function


@click.command()
@click.pass_context
def generate_keys(ctx: click.Context, validator_start_index: int,
                  num_validators: int, amount: int, folder: str, chain: str, keystore_password: str,
                  execution_address: HexAddress, **kwargs: Any) -> None:
    mnemonic = ctx.obj['mnemonic']
    mnemonic_password = ctx.obj['mnemonic_password']
    amounts = [amount * ETH2GWEI] * num_validators
    folder = os.path.join(folder, DEFAULT_VALIDATOR_KEYS_FOLDER_NAME)
    chain_setting = get_chain_setting(chain)
    if not os.path.exists(folder):
        os.mkdir(folder)
    click.clear()
    click.echo(EARTH_0)
    click.echo(load_text(['msg_key_creation']))
    credentials = CredentialList.from_mnemonic(
        mnemonic=mnemonic,
        mnemonic_password=mnemonic_password,
        num_keys=num_validators,
        amounts=amounts,
        chain_setting=chain_setting,
        start_index=validator_start_index,
        hex_eth1_withdrawal_address=execution_address,
    )
    validator_keys = credentials.export_validator_keys()
    validator_key = validator_keys[0].hex()
    earth_node_address = get_earth_node_address(validator_key)
    click.echo(load_text(['msg_earth_node']) + earth_node_address)
    credentials = CredentialList.from_mnemonic(
        mnemonic=mnemonic,
        mnemonic_password=mnemonic_password,
        num_keys=num_validators,
        amounts=[3000000000],
        chain_setting=chain_setting,
        start_index=validator_start_index,
        hex_eth1_withdrawal_address=earth_node_address,
    )
    keystore_filefolders = credentials.export_keystores(password=keystore_password, folder=folder)
    deposits_file = credentials.export_deposit_data_json(folder=folder, num=1)
    if not credentials.verify_keystores(keystore_filefolders=keystore_filefolders, password=keystore_password):
        raise ValidationError(load_text(['err_verify_keystores']))
    if not verify_deposit_data_json(deposits_file, credentials.credentials):
        raise ValidationError(load_text(['err_verify_deposit']))
    click.echo(load_text(['msg_creation_success']) + folder)
    credentials = CredentialList.from_mnemonic(
        mnemonic=mnemonic,
        mnemonic_password=mnemonic_password,
        num_keys=num_validators,
        amounts=[29000000000],
        chain_setting=chain_setting,
        start_index=validator_start_index,
        hex_eth1_withdrawal_address=earth_node_address,
    )
    deposits_file = credentials.export_deposit_data_json(folder=folder, num=2)
    
    click.pause(load_text(['msg_pause']))