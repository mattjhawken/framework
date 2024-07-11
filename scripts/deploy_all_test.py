from brownie import accounts, config, network, Contract, SmartnodesCore, TransparentProxy, ProxyAdmin, SmartnodesMultiSig
from scripts.helpful_scripts import get_account, encode_function_data, upgrade
from eth_abi import encode
from dotenv import load_dotenv, set_key
from web3 import Web3
import json
import time
import os

load_dotenv("..")

DEPLOY_NEW = True
UPGRADE = False


def deploy_proxy_admin(account):
    if DEPLOY_NEW:
        proxy_admin = ProxyAdmin.deploy({"from": account})
        proxy_address = proxy_admin.address
    else:
        proxy_address = os.getenv("SMARTNODES_ADMIN_ADDRESS")

        if proxy_address:
            proxy_admin = Contract.from_abi("SmartnodesProxyAdmin", proxy_address, ProxyAdmin.abi)
        else:
            raise "Proxy Admin contract not found!"
    
    set_key(".env", "SMARTNODES_ADMIN_ADDRESS", proxy_address)
    return proxy_admin


def deploy_smartnodes(account, proxy_admin):
    if DEPLOY_NEW:
        sno = SmartnodesCore.deploy({"from": account})
        
        encoded_init_function = encode_function_data(initializer=sno.initialize)
        
        sno_proxy = TransparentProxy.deploy(
            sno.address,
            proxy_admin.address,
            encoded_init_function,
            {"from": account}
        )
        sno_proxy = Contract.from_abi("SmartnodesCore", sno_proxy.address, SmartnodesCore.abi)
        smartnodes_address = sno_proxy.address
    else:
        smartnodes_address = os.getenv("SMARTNODES_ADDRESS")

        if smartnodes_address:
            sno_proxy = Contract.from_abi("SmartnodesCore", smartnodes_address, SmartnodesCore.abi)
        else:
            raise "SmartnodesCore contract not found!"
    
    set_key(".env", "SMARTNODES_ADDRESS", smartnodes_address)    
    return sno_proxy


def deploy_smartnodesValidator(account, proxy_admin):
    if DEPLOY_NEW:
        sno_multisig = SmartnodesMultiSig.deploy({"from": account})

        encoded_init_function = encode_function_data(initializer=sno_multisig.initialize)

        sno_multisig_proxy = TransparentProxy.deploy(
            sno_multisig.address,
            proxy_admin.address,
            encoded_init_function,
            {"from": account}
        )
        sno_multisig_proxy = Contract.from_abi("SmartnodesMultiSig", sno_multisig_proxy.address, SmartnodesMultiSig.abi)
        smartnodes_multisig_address = sno_multisig_proxy.address

    else:
        smartnodes_multisig_address = os.getenv("SMARTNODES_MULTISIG_ADDRESS")

        if smartnodes_multisig_address:
            sno_multisig_proxy = Contract.from_abi("SmartnodesMultiSig", smartnodes_multisig_address, SmartnodesMultiSig.abi)
        else:
            raise "SmartnodesMultiSig contract not found!"

    set_key(".env", "SMARTNODES_MULTISIG_ADDRESS", smartnodes_multisig_address)
    return sno_multisig_proxy


def initialize_contracts(account, core, multisig):
    if DEPLOY_NEW:
        core.initialize(accounts[:3], account, {'from': account})
        multisig.initialize(core.address, {"from": account})
        core.setValidatorContract(multisig, {"from": account})


def main():
    # Account to deploy the proxy (proxy admin, to become a DAO of sorts)
    account = accounts[0]

    proxy_admin = deploy_proxy_admin(account)
    sno = deploy_smartnodes(account, proxy_admin)
    sno_multisig = deploy_smartnodesValidator(account, proxy_admin)
    initialize_contracts(account, sno, sno_multisig)

    # Deploy a user and validator
    if DEPLOY_NEW:
        sno.approve(account, 100_000e18, {"from": account})
        sno.createValidator(
            "21c99fa3c263570d20132c24ef1b347e1b8afcdcfe88c303fb1f45b84b387a5b",
            50_000e18,
            {"from": account}
        )
        sno_multisig.addValidator(account, {"from": account})
        
        sno.approve(accounts[1], 100_000e18, {"from": accounts[1]})
        sno.createValidator(
            "21c99fa3c263570d20132c24ef1b347e1b8afcdcfe88c303fb1f45b84b387a5b",
            50_000e18,
            {"from": accounts[1]}
        )
        sno_multisig.addValidator(accounts[1], {"from": accounts[1]})
        
        sno.approve(accounts[2], 100_000e18, {"from": accounts[2]})
        sno.createValidator(
            "21c99fa3c263570d20132c24ef1b347e1b8afcdcfe88c303fb1f45b84b387a5b",
            50_000e18,
            {"from": accounts[2]}
        )
        sno_multisig.addValidator(accounts[2], {"from": accounts[2]})

        sno.createUser(
            "0d976b7e1fd59537000313e274dc6a9d035ebaf95f4b8857740f7c799abd8629",
            {"from": accounts[4]}
        )

    print(f"Validator: {sno.validators(1)}")
    print(f"User: {sno.users(1)}")
    print(f"Job: {sno.jobs(1)}")
    print(f"Proposal: {sno_multisig.proposals(0)}")
    
    job_id = 1
    worker_addresses = [accounts[3].address, accounts[0].address]
    
    
    # Finish job + payouts
    calldata1 = [[1], [encode(
        ["uint256", "address[]"],
        [job_id, worker_addresses]
    )]]

    # Remove validator
    calldata2 = [[0], [encode(["address"], [accounts[2].address])]]

    # Job creation test
    sno.requestJob([int(1e9), int(1e9)], {"from": accounts[4]})

    # Job completion test
    sno_multisig.createProposal(calldata1[0], calldata1[1], {"from": account})
    sno_multisig.approveTransaction(0, {"from": account})
    sno_multisig.approveTransaction(0, {"from": accounts[2]})

    # Test remove a validator
    sno_multisig.createProposal(calldata2[0], calldata2[1], {"from": accounts[1]})
    sno_multisig.approveTransaction(1, {"from": account})
    sno_multisig.approveTransaction(1, {"from": accounts[2]})
    
    sno.unlockTokens(10e18, {"from": account})

    print("\n_________________Final Contract State_________________")
    print(f"Validators: {sno.validators(1)}, {sno.validators(2)}, {sno.validators(3)}")
    print(f"User: {sno.users(1)}")
    print(f"Job: {sno.jobs(1)}")
    print(f"Proposal: {sno_multisig.proposals(0)}")
