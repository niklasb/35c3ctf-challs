pragma solidity ^0.5.0;

contract Bank {
    mapping(address => bool) public isOwner;

    constructor() public {
        isOwner[msg.sender] = true;
    }

    function select(uint256 addr) external view returns (uint256 res) {
        require(addr >= 100 && addr <= 104);
        assembly {
            res := sload(addr)
        }
    }

    function runTx(address code) external {
        require(isOwner[msg.sender]);
        (bool result,) = code.delegatecall("");
        require(result);
    }

    event FlagRequested();

    // called by server in response to FlagRequested event
    function setFlag(uint256 flag1, uint256 flag2) external {
        assembly {
            sstore(100, flag1)
            sstore(101, flag2)
        }
    }
}
