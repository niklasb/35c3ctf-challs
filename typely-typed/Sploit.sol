pragma solidity ^0.5.0;

contract Sploit {
    event FlagRequested();
    function () external {
        emit FlagRequested();
    }
}
