"""Exact generated-only atomic no-exposure witness; no runtime skip wiring."""
import argparse
import hashlib
import json
from pathlib import Path
from research.phase6.full_runner_build import materialize as base, once

PREFIX = 'polybot-core/src/main/java/com/polybot/hft/'
SESSION = PREFIX+'paper/ResearchSession.java'
MATCHER = PREFIX+'paper/PaperMatchingEngine.java'
LEDGER = PREFIX+'risk/AccountLedger.java'
STATE = PREFIX+'state/AtomicJsonState.java'
FREEZE = Path('research/phase6/atomic-guard-freeze.json')

WITNESS = '''
  private boolean researchRecoveredCheckpoint;
  /** Research witness valid ONLY inside the atomic callback. No execution labels. */
  static final class NoOrderWitness {
    private final ResearchSession owner;
    private final Thread thread=Thread.currentThread();
    private boolean active=true;
    private NoOrderWitness(ResearchSession owner){this.owner=owner;}
    void requireValid(){
      if(!active||thread!=Thread.currentThread()||!Thread.holdsLock(owner)
          ||!Thread.holdsLock(owner.ledger)||!Thread.holdsLock(owner.matching)
          ||!Thread.holdsLock(owner.checkpoint))
        throw new IllegalStateException("Expired/non-atomic no-order witness");
    }
  }
  synchronized <T> T withResearchNoOrderWitness(java.util.function.Function<NoOrderWitness,T> action) {
    java.util.Objects.requireNonNull(action);
    synchronized(ledger){synchronized(matching){synchronized(checkpoint){
      var state=ledger.snapshot();
      if(externalMode||researchRecoveredCheckpoint||failed||entryStopped||state.halted()||!pending.isEmpty()
          ||!unhedged.isEmpty()||!matching.researchHasNoOrders()
          ||!ledger.researchPersistenceHealthy()||!checkpoint.researchHealthy()
          ||state.holdings().values().stream().anyMatch(h->h.shares().signum()!=0||h.basis().signum()!=0)
          ||state.orders().values().stream().anyMatch(o->o.remaining().signum()!=0
              ||!java.util.Set.of("CANCELED","FILLED","REJECTED").contains(o.status())))
        throw new IllegalStateException("No-order research witness requires healthy empty exposure");
      var witness=new NoOrderWitness(this);
      try{return action.apply(witness);}
      finally{witness.active=false;}
    }}}
  }

'''


def render(path, text):
    if path == SESSION:
        text = once(text, '    JsonNode saved = checkpoint.load();',
                    '    JsonNode saved = checkpoint.load();\n    researchRecoveredCheckpoint = saved != null;')
        return once(text, '  public synchronized List<ResearchMarket> markets() {',
                    WITNESS+'  public synchronized List<ResearchMarket> markets() {')
    if path == MATCHER:
        return once(text, '  public synchronized List<Map<String, Object>> diagnostics() {',
                    '  synchronized boolean researchHasNoOrders(){return orders.isEmpty();}\n\n'
                    '  public synchronized List<Map<String, Object>> diagnostics() {')
    if path == LEDGER:
        text = once(text, '  private boolean failed;', '  private boolean failed;\n  private final boolean researchRestored;')
        text = once(text, '    var node = file.load();', '    var node = file.load();\n    researchRestored = node != null;')
        text = once(text, '  public synchronized boolean persistenceFailed() {',
                    '  public synchronized boolean researchPersistenceHealthy(){return !failed && !researchRestored && file.researchHealthy();}\n\n'
                    '  public synchronized boolean persistenceFailed() {')
        return once(text, '  public void close() {', '  public synchronized void close() {')
    if path == STATE:
        text = once(text, '  private final Path path;', '  private boolean researchWriteFailed;\n  private final Path path;')
        text = once(text, '  public synchronized void save(Object state) {',
                    '  public synchronized boolean researchHealthy(){return !researchWriteFailed && channel.isOpen() && lock.isValid();}\n\n'
                    '  public synchronized void save(Object state) {\n'
                    '    if(!researchHealthy())throw new IllegalStateException("Research state is unhealthy");')
        text = once(text, '      throw new IllegalStateException("Durable write failed", e);',
                    '      researchWriteFailed=true;\n      throw new IllegalStateException("Durable write failed", e);')
        return once(text, '  public void close() {', '  public synchronized void close() {')
    raise ValueError('Unexpected generated target')


def materialize(output):
    spec = json.loads(FREEZE.read_bytes())
    for path, sha in spec['inputsSha256'].items():
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
            raise ValueError('Changed frozen guard input '+path)
    provenance = base(output); root = Path(output)
    for path in (SESSION, MATCHER, LEDGER, STATE):
        target = root/path
        if hashlib.sha256(target.read_bytes()).hexdigest() != spec['prefixSourcesSha256'][path]:
            raise ValueError('Changed generated prefix '+path)
        raw = render(path, target.read_text()).encode()
        if hashlib.sha256(raw).hexdigest() != spec['generatedSourcesSha256'][path]:
            raise ValueError('Changed generated atomic guard '+path)
        target.write_bytes(raw)
    result = dict(scope='GENERATED_ATOMIC_EMPTY_EXPOSURE_WITNESS_NOT_RUNTIME_SKIP',
                  defaultCoreFilesModified=0, generatedFilesChanged=4,
                  guardCallbackImplemented=True, identityConsumerIntegrated=False,
                  noOrderExecutionSkipImplemented=False, marketNetPnlRecomputed=False,
                  independentPaperQualificationAllowed=False, liveAllowed=False,
                  prefix=provenance)
    (root/'atomic-guard-provenance.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--output', required=True); args = p.parse_args()
    print(json.dumps(materialize(args.output), indent=2))
