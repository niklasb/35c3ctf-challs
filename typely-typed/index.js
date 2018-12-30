const ethjsUtil = require('ethereumjs-util');
const EthjsTx = require('ethereumjs-tx');
const Web3 = require('web3');
const fs = require('fs');
const solc = require('solc');

const web3 = new Web3(
  new Web3.providers.HttpProvider('http://localhost:8545'));

const dbContract = fs.readFileSync('DB.sol').toString();

const scriptContract = fs.readFileSync('evm.hex').toString();

var input = {
    language: 'Solidity',
    sources: { 'DB.sol': { content: dbContract } },
    settings: {
        outputSelection: {
            '*': {
                '*': [ '*' ]
            }
        }
    }
}

const output = JSON.parse(solc.compile(JSON.stringify(input)));
const solDB = output.contracts['DB.sol']['DB']

// learn ride remove recycle rocket parade bone bubble fancy toward inject cradle nose domain bird
// pubkey: 0x03e034ff984879b115417334e22c12424574f996ef853e7b6b0a29c985fa4394c0
const admin = '0x03f46475C4b79986Cb9E618Ec7F79C2f326CBEC0';
const adminPrivkey = '0xa728299cbb9cd5a107ef19919e4648e4db88fade63eaea9cb32ffc1c9b17d44c';
const adminPassword = 'awsdjasdaskdaksjdakdwqhdsdlaksd';

// today left depart cave rotate yellow maple stone symptom surround catch uniform cave motion neither
const acc = '0x544e3941ef92d6b2da1335afb8b203b1706bdea9';

const privkeys = {
  '0x03f46475C4b79986Cb9E618Ec7F79C2f326CBEC0':
      'a728299cbb9cd5a107ef19919e4648e4db88fade63eaea9cb32ffc1c9b17d44c'
};

const raw = async (from, to, dat, value=0) => {
  const tx = {
    from: from,
    to: to,
    data: dat,
    gas: 3000000,
    gasPrice: '10000',
    value: value,
  };
  return await web3.eth.sendTransaction(tx);
}

const rawSigned = async (from, to, dat, value=0) => {
  let privkey = privkeys[from];
  let nonce = await web3.eth.getTransactionCount(from);

  let tx = new EthjsTx({
    nonce: nonce,
    from: from,
    to: to,
    data: dat,
    gas: 3000000,
    gasPrice: '10000',
    value: value,
  });
  tx.sign(Buffer.from(privkey, 'hex'));
  let raw = '0x' + tx.serialize().toString('hex');
  return await web3.eth.sendSignedTransaction(raw);
}

const getNextContractAddr = async (acc) => {
  return ethjsUtil.bufferToHex(ethjsUtil.generateAddress(
      acc,
      await web3.eth.getTransactionCount(acc)));
}

const abi = solDB.abi;
const bytecode = solDB.evm.bytecode.object;
const DB = new web3.eth.Contract(abi, {data: bytecode});

const importAdmin = async () => {
  await web3.eth.personal.importRawKey(adminPrivkey, adminPassword);
  await web3.eth.personal.unlockAccount(admin, adminPassword);
}

const prepare = async () => {
  //await importAdmin();
  //const abi = solDB.abi;
  //const bytecode = solDB.evm.bytecode.object;
  //let DB = new web3.eth.Contract(abi, {from: admin, data: bytecode, gas: 2000000});
  //DB = await DB.deploy();
  //
  //await web3.eth.personal.lockAccount(admin);

  await raw(acc, admin, null, web3.utils.toWei('50', 'ether'));
  let data = await DB.deploy({from: admin})._deployData;
  let dbAddr = await getNextContractAddr(admin);
  await rawSigned(admin, null, '0x' + data);
  return dbAddr;
}

const main = async () => {
  let dbAddress = await prepare();
  console.log('DB @ ' + dbAddress);
  DB.options.address = dbAddress;
  DB.options.from = acc;

  let contractAddr = await getNextContractAddr(acc);
  await raw(acc, null, '0x' + scriptContract);
  console.log(await web3.eth.getCode(contractAddr));

  console.log(await DB.methods.isOwner(acc).call());

  await importAdmin();
  await DB.methods.runTx(contractAddr).send({from: admin});
  return;
  const addr = web3.utils.soliditySha3(
    {type: 'uint256', value: acc},
    {type: 'uint256', value: 0});
  console.log(addr);
  //console.log(await web3.eth.getStorageAt(DB.options.address, addr));
  console.log(await DB.methods.isOwner(acc).call());
}

main().then(() => {})
