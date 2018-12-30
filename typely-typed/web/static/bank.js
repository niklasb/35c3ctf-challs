let bank_address = '0x4836D27fC5397854Db3eEc3BefEAb299cA19338f';
// event FlagRequested();
let FlagRequested = '0xa167172562add270a4b89c49b58bcae0b13d3206fca06345a091d6ec738878c5';
let check_interval = 1500;

let bank = null;
let config = null;

async function loadConfig() {
  if (config === null) {
    config = await (await fetch(`/config`)).json()
  }
}

async function spawn() {
  let button = $('#spawn-button');
  button.addClass('hidden');
  let status = $('#spawn-status');
  status.removeClass('hidden');
  status.text('Computing PoW...');

  let proof = await getProof(status);
  let res = await (await fetch('/spawn', {
    method: 'POST',
    body: JSON.stringify({'proof': proof}),
  })).json();
  let id = res.id;
  document.location = `/bank/#${id}`;
}

function setStatus(status) {
  $('#status').html(status);
}

var guid = (function() {
  function s4() {
    return Math.floor((1 + Math.random()) * 0x10000)
    .toString(16)
    .substring(1);
  }
  return function() {
    return s4() + s4() + '-' + s4() + '-' + s4() + '-' +
        s4() + '-' + s4() + s4() + s4();
  };
})();

async function getProof(status = null) {
  if (status !== null) {
    status.text('Computing PoW...');
  }
  await loadConfig();
  let hashcash = await (new Promise((resolve, reject) => {
    let res;
    opts = {
      hashcashUrl: 'https://hashcash.io',
      readyCb: () => resolve(res),
    };
    res = new HashcashIO(opts);
  }));

  let id = guid();
  return await (new Promise((resolve, reject) => {
    hashcash.calculate({
      id: id,
      limit: config.complexity,
      publicKey: '9ddb6576-43e6-4fee-8263-1c34d9afac98',
      done: function() {
        resolve(id);
      },
      progress: function(totalDone) {
        if (status !== null) {
          status.text(`Computing PoW ${Math.round(Math.min(totalDone / config.complexity, 1) * 1000) / 10}%...`);
        } else {
          console.log(`PoW progress: ${totalDone}`);
        }
      },
    });
  }));
}

class Account {
  constructor(bank, num) {
    this.bank = bank;
    this.num = num;
  }

  async getBalance() {
    let req = {
      'jsonrpc': '2.0',
      'method': 'eth_getStorageAt',
      'params': [
        bank_address,
        `0x${this.num.toString(16)}`,
        'latest'
      ],
      'id': 0,
    };
    let resp = await (await fetch(`/eth/${this.bank.id}`, {
      method: 'POST',
      body: JSON.stringify(req),
      headers: {
        'Content-Type': 'application/json',
      }
    })).json();
    return parseInt(resp.result, 16);
  }

  async render() {
    let balance = await this.getBalance();
    return `
      <tr id='${this.num}'>
        <td>${this.num}</td>
        <td>${balance}</td>
      </tr>`;
  }
}

class Bank {
  constructor(id) {
    this.id = id;
    this.accounts = [100,101,102,103,104].map((num) => new Account(this, num));
  }

  async renderAccountTable() {
    let html = `
      <table>
        <thead>
          <tr>
            <th>Account number</th>
            <th>Balance</th>
          </tr>
        </head>
        <tbody>
        `;
    for (var i = 0; i < this.accounts.length; ++i) {
      html += await this.accounts[i].render();
    }
    html += '</tbody></table>';
    return html;
  }
}

async function runScript(script, button, status) {
  button.addClass('hidden');
  status.removeClass('hidden');
  status.text('Computing PoW...');
  let proof = await getProof(status);
  status.text('Processing...');
  let req = {'script': script, 'id': bank.id, 'proof': proof};
  let resp = await (await fetch('/execute', {method: 'POST', body: JSON.stringify(req)})).json();
  button.removeClass('hidden');
  status.text(`Result: ${resp.result}`);
  await update();
}

async function deposit() {
  let acc = $('#deposit-acc').val();
  let amount = $('#deposit-amount').val();
  await runScript(`
      MAX_BALANCE = 1000000000
      acc = ${acc}
      amount = ${amount}

      bal = boundscheck(getBalance(acc), 0, MAX_BALANCE - amount)
      setBalance(acc, bal + amount)
      `, $('#deposit-button'), $('#deposit-status'));
}

async function transfer() {
  let from = $('#transfer-from').val();
  let to = $('#transfer-to').val();
  let amount = $('#transfer-amount').val();
  await runScript(`
    MAX_BALANCE = 1000000000
    from = ${from}
    to = ${to}
    amount = ${amount}

    bal_from = boundscheck(getBalance(from), amount, MAX_BALANCE)
    bal_to = boundscheck(getBalance(to), 0, MAX_BALANCE - amount)
    setBalance(from, bal_from - amount)
    setBalance(to, bal_to + amount)
    `, $('#transfer-button'), $('#transfer-status'));
}

async function checkFlagRequested() {
  let req = {
    'jsonrpc': '2.0',
    'method': 'eth_getLogs',
    'params': [
      {
        'address': bank_address,
        'fromBlock': '0x0',
        'toBlock': 'latest'
      }
    ],
    'id': 0
  };

  let resp = await (await fetch(`/eth/${bank.id}`, {
    method: 'POST',
    body: JSON.stringify(req),
    headers: {
      'Content-Type': 'application/json',
    }
  })).json();

  let found = false;
  resp.result.forEach((res) => {
    res.topics.forEach((topic) => {
      if (topic == FlagRequested)
        found = true;
    });
  });
  return found;
}

async function update() {
  let res = await (await fetch(`/status/${bank.id}`)).json()
  if (res.status === 'queued') {
    setStatus(`Waiting in queue (position: ${res.position})...`);
    return;
  }
  if (res.status === 'setup') {
    setStatus('Setting up your bank...');
    return;
  }
  if (res.status === 'dead') {
    setStatus('Your bank expired, try <a href="/">creating a new one</a>!');
    $('#bank').addClass('hidden');
    return;
  }

  check_interval = 5000;

  $('#bank').removeClass('hidden');
  setStatus(
    `Your bank is running smoothly, for at least
      another ${Math.round(res.time_left)} seconds`);

  $('#accounts').html(await bank.renderAccountTable());

  let flagRequested = await checkFlagRequested();
  if (flagRequested) {
    $('#flag-status').text(
        'Flag has been requested, it should arrive very soon');
  }
}

function check() {
  setTimeout(check, check_interval);
  update();
}

function start() {
  bank_id = document.location.hash.slice(1);
  if (!bank_id.match(/^[a-f0-9]{32}$/)) {
    alert('Invalid bank!');
    return;
  }
  bank = new Bank(bank_id);

  setStatus('Setting up...');
  check();
}
