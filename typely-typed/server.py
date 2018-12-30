#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
import tornado.httpclient
import tornado.tcpserver

import argparse, hashlib, os, sys, signal, socket, tempfile, random, \
        subprocess, json, time, atexit, traceback, functools

import chain
import compiler

ROOT = os.path.dirname(os.path.abspath(__file__))
TMP_DIR = ROOT + '/tmp/'

def load_complexity():
    global COMPLEXITY
    COMPLEXITY = float(open(ROOT + '/web/complexity.txt').read())

def setup():
    print('Root dir: %s' % ROOT)
    if not os.path.exists(TMP_DIR):
        os.makedirs(TMP_DIR)
    load_complexity()

def randstr():
    return hashlib.md5(os.urandom(32)).hexdigest()

def instance_dir(identifier):
    return TMP_DIR + '/' +  identifier

MNEM = ('today left depart cave rotate yellow maple stone symptom '
    'surround catch uniform cave motion neither')

class Instance(object):
    def __init__(self, identifier):
        self.identifier = identifier
        self.dir = instance_dir(self.identifier)
        os.makedirs(self.dir)
        self.timed_out = False
        self.start_time = None
        self.timeout_killer = None

    def run(self):
        print('%s: Running' % self.identifier)

    def start(self, num):
        self.num = num
        self.port = 10000 + num
        assert self.port < 20000

        print('%s: Starting (port=%d)...' % (self.identifier, self.port))
        self.start_time = time.time()

        kw = dict(stdout=subprocess.DEVNULL)
        if DEBUG:
            print('%s: Starting in DEBUG mode' % self.identifier)
            kw = {}

        self.proc = subprocess.Popen([
                './node_modules/.bin/ganache-cli',
                '-a', '1',
                '-m', MNEM,
                '-h', '127.0.0.1',
                '-p', str(self.port),
            ] + (['--debug'] if DEBUG else []),
            cwd=ROOT,
            preexec_fn=os.setsid,
            **kw)

        self.conn = chain.Connection(self.get_rpc_url())
        print('%s: Waiting for node to come live' % self.identifier)
        self.conn.wait()

        print('%s: Preparing chain state...' % self.identifier)
        self.conn.prepare()
        print('%s: Bank address: %s' % (self.identifier, self.conn.get_bank_addr()))
        print('%s: Fully set up' % self.identifier)

        self.timeout_killer = tornado.ioloop.IOLoop.current().call_later(
                TIMEOUT, lambda: self.kill(timed_out=True))

    def get_rpc_url(self):
        return 'http://127.0.0.1:%d' % self.port

    def unschedule_timeout(self):
        if self.timeout_killer is not None:
            tornado.ioloop.IOLoop.current().remove_timeout(self.timeout_killer)
            self.timeout_killer = None

    def kill(self, timed_out=False):
        print('%s: Killing' % self.identifier)
        self.unschedule_timeout()
        os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        self.timed_out = True

    def check(self):
        self.proc.poll()
        if self.proc.returncode == None:
            try:
                if self.conn.check():
                    print('%s: Sending flag!' % self.identifier)
            except:
                # there is a slim chance the process got killed
                # in the meantime
                pass
            return None
        self.unschedule_timeout()
        return True


class Queue(object):
    def __init__(self):
        self.active = {}
        self.todo = []
        self.schedule()
        self.setting_up = set()
        atexit.register(self.clear)

    def clear(self):
        print('QUEUE: Cleaning up %d instances' % len(self.active))
        for instance in self.active.values():
            try:
                instance.kill()
            except:
                print('QUEUE: Error while killing %s' % instance.identifier)
                traceback.print_exc()
                pass

    def schedule(self):
        tornado.ioloop.IOLoop.current().call_later(2, self.check)

    def check(self):
        active = {}
        for id in self.active:
            instance = self.active[id]
            try:
                done = instance.check()
            except:
                print('QUEUE: Exception during check:')
                traceback.print_exc()
                done = True
            if done:
                print('QUEUE: Instance %s is done' % instance.identifier)
            else:
                active[id] = instance
        self.active = active

        if len(self.active) < MAX_ACTIVE and self.todo:
            space = MAX_ACTIVE - len(self.active)
            to_start, self.todo = self.todo[:space], self.todo[space:]
            self.setting_up = set(x.identifier for x in to_start)
            for instance in to_start:
                inuse = set(x.num for x in self.active.values())
                num = 1
                while num in inuse:
                    num += 1
                try:
                    instance.start(num)
                except:
                    traceback.print_exc()
                    print('QUEUE: Trying to kill...')
                    try:
                        instance.kill()
                    except:
                        traceback.print_exc()
                        pass
                self.active[instance.identifier] = instance
                self.setting_up.remove(instance.identifier)

        self.schedule()

    def add(self, instance):
        print('QUEUE: Adding instance %s' % instance.identifier)
        self.todo.append(instance)

    def get_status(self, id):
        todoidx = next((i for i in range(len(self.todo))
            if self.todo[i].identifier == id), None)
        if todoidx is not None:
            return {'status': 'queued', 'position': todoidx}
        if id in self.setting_up:
            return {'status': 'setup'}
        if id in self.active:
            instance = self.active[id]
            time_left = TIMEOUT - (time.time() - instance.start_time)
            return {'status': 'live', 'time_left': time_left}
        return {'status': 'dead'}

    def get_instance(self, id):
        return self.active.get(id)


class ReqHandler(tornado.web.RequestHandler):
    def nocache(self):
        self.set_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.set_header('Pragma', 'no-cache')
        self.set_header('Expires', '0')

    def respond_json(self, obj, status=200):
        self.set_status(status)
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        self.nocache()
        self.write(json.dumps(obj))
        self.finish()

    def check_pow(self, hcid, cb):
        if NO_POW:
            return cb()

        hcid = str(hcid)
        assert not '/' in hcid and not '.' in hcid

        self.pow_cb = cb

        url = ('https://hashcash.io/api/checkwork/' + hcid
                + '?apikey=PRIVATE-1f0236ac-eec7-4fcd-b2b5-2495fb115d8a')
        tornado.httpclient.AsyncHTTPClient().fetch(url,
                    callback=self._on_hashcash_response)

    def _powfail(self):
        return self.respond_json({'result': 'invalid_proof_of_work'}, status=403)

    def _on_hashcash_response(self, response):
        if response.error:
            return self._powfail()
        work = tornado.escape.json_decode(response.body)
        if work['totalDone'] < COMPLEXITY or work['verified']:
            return self._powfail()
        self.pow_cb()


class UpdateComplexity(tornado.web.RequestHandler):
    def get(self):
        load_complexity()
        self.write('ok')


USAGE = '''API examples:

{"id": "<ID>", "script": "setBalance(100, 1337)", "proof": "<POW>"}
{"script": "setBalance(100, 1337), "debug": true} # no PoW required
'''

class ExecuteHandler(ReqHandler):
    @tornado.web.asynchronous
    def post(self):
        req = json.loads(self.request.body)

        identifier = req.get('id')
        script = req.get('script')
        dbg = req.get('debug')

        if not (script and dbg or identifier):
            return self.respond_json({
                'result': 'invalid_params',
                'help': USAGE},
                status=500)

        script = str(script)

        try:
            hsk = compiler.script_to_hsk(script)
        except:
            # traceback.print_exc()
            return self.respond_json({
                'result': 'syntax_error',
                'help': USAGE,
                })

        if dbg:
            return self.respond_json({
                'result': 'success',
                'generated_code': hsk,
            })

        identifier = str(identifier)
        instance = queue.get_instance(identifier)
        if instance is None:
            return self.respond_json({'result': 'unknown_id'}, status=404)

        proof = req.get('proof')
        self.check_pow(proof, functools.partial(
            self.on_good_pow, instance, hsk))

    def _powfail(self):
        return self.respond_json({
            'result': 'invalid_proof_of_work',
            'help': USAGE}, status=403)

    def on_good_pow(self, instance, hsk):
        try:
            evmcode = compiler.run_hsk(hsk, timeout=HSK_TIMEOUT)
        except compiler.HskTypeError:
            return self.respond_json({
                'result': 'type_error',
                'help': USAGE,
                })
        except subprocess.TimeoutExpired:
            return self.respond_json({
                'result': 'timeout',
                'help': USAGE,
                })

        res = instance.conn.run_code(evmcode)
        if res:
            return self.respond_json({'result': 'success'})
        else:
            return self.respond_json({'result': 'runtime_error'})


class SpawnHandler(ReqHandler):
    @tornado.web.asynchronous
    def post(self):
        req = json.loads(self.request.body)
        proof = req.get('proof')
        self.check_pow(proof, self.on_good_pow)

    def on_good_pow(self):
        identifier = randstr()
        queue.add(Instance(identifier))
        return self.respond_json({'result': 'success', 'id': identifier})


class StatusHandler(ReqHandler):
    def get(self, identifier):
        res = queue.get_status(identifier)
        return self.respond_json(res)

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        res = open(ROOT + '/web/templates/index.html').read()
        self.write(res)
        self.set_header('Content-Type', 'text/html; charset=utf-8')

class BankHandler(tornado.web.RequestHandler):
    def get(self):
        res = open(ROOT + '/web/templates/bank.html').read()
        self.write(res)
        self.set_header('Content-Type', 'text/html; charset=utf-8')

class ConfigHandler(ReqHandler):
    def get(self):
        return self.respond_json({'complexity': COMPLEXITY})

def is_unique_list(lst):
    return len(lst) == len(set(lst))

class EthHandler(tornado.web.RequestHandler):
    ETH_METHOD_BLACKLIST = [
        'debug_',
        'bzz_',
        'eth_new',
        'eth_mining',
        'eth_subscribe',
        'eth_unsubscribe',
        'eth_sync',
        'eth_uninstallFilter',
        'net_',
        'miner_',
        'personal_unlockAccount',
        'shh_',
        'rpc_',
    ]

    def eth_method_is_blacklisted(self, meth):
        return any(meth.startswith(x) for x in self.__class__.ETH_METHOD_BLACKLIST)

    def _on_upstream_response(self, resp):
        if resp.error and not isinstance(resp.error, tornado.httpclient.HTTPError):
            self.set_status(500)
            self.write('Internal server error')
            self.finish()
            return

        self.set_status(resp.code)
        self._headers = tornado.httputil.HTTPHeaders()
        for header, v in resp.headers.get_all():
            if header not in (
                    'Content-Length',
                    'Transfer-Encoding',
                    'Content-Encoding',
                    'Connection'):
                self.add_header(header, v)

        if resp.body:
            self.set_header('Content-Length', len(resp.body))
            self.write(resp.body)
        self.finish()

    # inspired by https://github.com/senko/tornado-proxy/blob/master/tornado_proxy/proxy.py
    @tornado.web.asynchronous
    def post(self, identifier):
        instance = queue.get_instance(identifier)
        if instance is None:
            self.set_status(404)
            self.write('Unknown ID')
            self.finish()
            return

        def hook(pairs):
            assert is_unique_list([k for k,v in pairs])
            return dict(pairs)
        req = json.loads(self.request.body, object_pairs_hook=hook)

        url = instance.get_rpc_url()
        # print('%s: RPC url=%s request=%s' % (identifier, url, req))

        if self.eth_method_is_blacklisted(req['method']):
            self.set_status(403)
            self.write('method "%s" is blacklisted' % req['method'])
            self.finish()
            return

        kwargs = dict(
            method='POST',
            body=json.dumps(req))

        req = tornado.httpclient.HTTPRequest(url, **kwargs)
        client = tornado.httpclient.AsyncHTTPClient()
        client.fetch(req, self._on_upstream_response, raise_error=False)

def make_webapp():
    return tornado.web.Application([
        (r'/', IndexHandler),
        (r'/bank/', BankHandler),
        (r'/spawn', SpawnHandler),
        (r'/config', ConfigHandler),
        (r'/execute', ExecuteHandler),
        (r'/update_complexity', UpdateComplexity),
        (r'/eth/([0-9a-f-]+)', EthHandler),
        (r'/status/([0-9a-f-]+)', StatusHandler),
        (r'/static/(.+)', tornado.web.StaticFileHandler, {'path': ROOT + '/web/static'}),
    ])

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--nopow', action='store_true')
    p.add_argument('--chain_timeout', type=int, default=3*60)
    p.add_argument('--hsk_timeout', type=int, default=30)
    p.add_argument('--max_active', type=int, default=100)
    p.add_argument('--host', default='127.0.0.1')
    p.add_argument('--complexity', type=float)
    p.add_argument('--debug', action='store_true')
    p.add_argument('--port', dest='port', type=int, default=9000)
    args = p.parse_args()

    NO_POW = args.nopow
    TIMEOUT = args.chain_timeout
    HSK_TIMEOUT = args.hsk_timeout
    MAX_ACTIVE = args.max_active
    DEBUG = args.debug

    setup()
    if args.complexity != None:
        COMPLEXITY = args.complexity

    queue = Queue()

    webapp = make_webapp()
    print('Starting on %s:%d' % (args.host, args.port))
    webapp.listen(args.port, address=args.host)

    tornado.ioloop.IOLoop.current().start()
