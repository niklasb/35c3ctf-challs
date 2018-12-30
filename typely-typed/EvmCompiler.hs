{-# LANGUAGE -- the good stuff
  ConstraintKinds, DataKinds, FlexibleContexts, GADTs, LambdaCase,
  OverloadedStrings, PolyKinds, ScopedTypeVariables, TypeFamilies,
  TypeOperators, UndecidableInstances, UnicodeSyntax #-}

import Control.Arrow ((&&&), (***)) -- we really just use these to mess with people
import Data.Proxy
import Data.Type.Bool
import GHC.TypeLits hiding (Mod)
import Prelude hiding (LT, GT)
import Unsafe.Coerce (unsafeCoerce)
import qualified Data.ByteString as BS
import qualified Data.Foldable as F
import qualified Data.List as L
import qualified Data.Sequence as Seq
import qualified GHC.TypeLits as T

data Range = Nat :⋯: Nat

type a ≤ b = a <= b
type a ≤? b = a <=? b
type a ≥ b = b ≤ a

-- Operations on ranges
type family (q ∷ Range) ➕ (r ∷ Range) ∷ Range where
  (a :⋯: b) ➕ (c :⋯: d) = (a + c) :⋯: (b + d)
type family (q ∷ Range) – (r ∷ Range) ∷ Range where
  (a :⋯: b) – (c :⋯: d) = (a - d) :⋯: (b - c)
type family (q ∷ Range) ∗ (r ∷ Range) ∷ Range where
  (a :⋯: b) ∗ (c :⋯: d) = (a T.* c) :⋯: (b T.* d)
type family (q ∷ Range) ÷ (r ∷ Range) ∷ Range where
  (a :⋯: b) ÷ (c :⋯: d) = 0 :⋯: (d - 1)

type family IsMinusSafe (q ∷ Range) (r ∷ Range) ∷ Bool where
  IsMinusSafe (a :⋯: b) (c :⋯: d) = d ≤? a

type family (q ∷ Range) ⊆? (r ∷ Range) ∷ Bool where
  (a :⋯: b) ⊆? (c :⋯: d) = c ≤? a && b ≤? d

class NonZero (r ∷ Range)
instance (lo ≥ 1) ⇒ NonZero (lo :⋯: hi)

type MinusIsSafe q r = IsMinusSafe q r ~ True
type q ⊆ r = (q ⊆? r) ~ True
type x ∈ r = (x :⋯: x) ⊆ r

-- Quick maths
type Equivs x = ( (x + 1 + 1 - 2) ~ x
                , (x + 1 - 1) ~ x
                , (x + 1 + 1) ~ (x + 2)
                , (x + 3) ~ (x + 2 + 1)
                , (x + 2 + 1 - 2 + 1) ~ (x + 2)
                )
type Equivs2 x y = (((x - y) + (y + 1)) ~ (x + 1))

-- A monad++ is like a burrito with a phantom type
class MonadPlusPlus m where
  ret ∷ a → m s s a
  (≻≻≈) ∷ m s s' a → (a → m s' s'' b) → m s s'' b

  (≻≻) ∷ m s s' a → m s' s'' b → m s s'' b
  ma ≻≻ mb = ma ≻≻≈ const mb

-- EVM program builder
type EvmRange = 0 :⋯: (2^256 - 1)
type EvmValue (v ∷ Nat) = v ∈ EvmRange

data EvmInstr (δ ∷ Nat) (α ∷ Nat) where
  ADD      ∷ EvmInstr 2 1
  MUL      ∷ EvmInstr 2 1
  SUB      ∷ EvmInstr 2 1
  MOD      ∷ EvmInstr 2 1
  LT       ∷ EvmInstr 2 1
  GT       ∷ EvmInstr 2 1
  ISZERO   ∷ EvmInstr 1 1
  OR       ∷ EvmInstr 2 1
  CODECOPY ∷ EvmInstr 3 0
  SLOAD    ∷ EvmInstr 1 1
  SSTORE   ∷ EvmInstr 2 0
  JUMP     ∷ EvmInstr 1 0
  JUMPI    ∷ EvmInstr 2 0
  PC       ∷ EvmInstr 0 1
  JUMPDEST ∷ EvmInstr 0 0
  PUSH     ∷ Integer → Integer → EvmInstr 0 1  -- width, value
  DUP      ∷ (α ~ (δ + 1), δ ≤ 16, KnownNat δ) ⇒ EvmInstr δ α
  RETURN   ∷ EvmInstr 2 0
  REVERT   ∷ EvmInstr 2 0

data SomeEvmInstr = ∀ δ α. SomeEvmInstr (EvmInstr δ α)

type EvmProgram = Seq.Seq SomeEvmInstr
data EvmState (depth ∷ Nat) = EvmState { evm_program ∷ EvmProgram }

emptyEvmState ∷ EvmState 0
emptyEvmState = EvmState Seq.empty

newtype EvmBuilder (depth ∷ Nat) (depth' ∷ Nat) a
  = EvmBuilder { runEvmBuilder ∷ EvmState depth → (a, EvmState depth') }

execEvmBuilder ∷ EvmBuilder 0 depth a → EvmProgram
execEvmBuilder builder = evm_program (snd (runEvmBuilder builder emptyEvmState))

instance MonadPlusPlus EvmBuilder where
  ret x = EvmBuilder (const x &&& id)
  EvmBuilder f ≻≻≈ g = EvmBuilder (uncurry runEvmBuilder . (g *** id) . f)

modify ∷ (EvmState depth → EvmState depth') → EvmBuilder depth depth' ()
modify f = EvmBuilder (const () &&& f)

appendInstr ∷ EvmInstr δ α → EvmBuilder depth (depth - δ + α) ()
appendInstr instr =
  modify (\st → EvmState { evm_program = evm_program st Seq.|> SomeEvmInstr instr })

data StackValue (slot ∷ Nat) (r ∷ Range) = (r ⊆ EvmRange) ⇒ StackValue

makeStackValue ∷ (r ⊆ EvmRange) ⇒ EvmBuilder depth depth (StackValue slot r)
makeStackValue = ret StackValue

α1
  ∷ (r ⊆ EvmRange, α ~ 1, depth' ~ (depth - δ + α))
  ⇒ EvmInstr δ α
  → EvmBuilder depth depth' (StackValue (depth' - 1) r)
α1 ins = appendInstr ins ≻≻ makeStackValue

ignore ∷ EvmInstr δ α → EvmBuilder depth (depth - δ + α) ()
ignore ins = appendInstr ins

exitCode ∷ EvmBuilder depth depth' () → EvmBuilder depth depth ()
exitCode builder = builder ≻≻ modify unsafeCoerce -- this is fine

type DupIdx (slot ∷ Nat) (depth ∷ Nat) = depth - slot - 1

type CanBeDuped (slot ∷ Nat) (depth ∷ Nat) =
  ( DupIdx slot depth ≤ 16
  , DupIdx slot depth ≤ depth
  , KnownNat (DupIdx slot depth)
  , Equivs2 depth (DupIdx slot depth)
  )

evmDup
  ∷ ∀ δ depth.
    ( KnownNat δ
    , δ ≤ depth
    , δ ≤ 16
    , Equivs2 depth δ
    )
  ⇒ Proxy δ
  → EvmBuilder depth (depth + 1) ()
evmDup _ = ignore (DUP ∷ EvmInstr δ (δ + 1))

pushStackValue
  ∷ ∀ slot depth range. (CanBeDuped slot depth)
  ⇒ StackValue slot range
  → EvmBuilder depth (depth + 1) ()
pushStackValue _ = evmDup (Proxy ∷ Proxy (DupIdx slot depth))

mkPush ∷ Integer → EvmInstr 0 1
mkPush value = PUSH (head (filter (\x → 2^(x * 8) > value) [1..])) value

singleton
  ∷ (KnownNat x, EvmValue x, Equivs depth)
  ⇒ Proxy x
  → EvmBuilder depth (depth + 1) (StackValue depth (x :⋯: x))
singleton p = α1 (mkPush (natVal p))

(➕)
  ∷ ( CanBeDuped b depth
    , CanBeDuped a (depth + 1)
    , Equivs depth
    , (ra ➕ rb) ⊆ EvmRange)
  ⇒ StackValue a ra → StackValue b rb
  → EvmBuilder depth (depth + 1) (StackValue depth (ra ➕ rb))
a ➕ b = pushStackValue b ≻≻ pushStackValue a ≻≻ α1 ADD

(∗)
  ∷ ( CanBeDuped b depth
    , CanBeDuped a (depth + 1)
    , Equivs depth
    , (ra ∗ rb) ⊆ EvmRange)
  ⇒ StackValue a ra → StackValue b rb
  → EvmBuilder depth (depth + 1) (StackValue depth (ra ∗ rb))
a ∗ b = pushStackValue b ≻≻ pushStackValue a ≻≻ α1 MUL

(–)
  ∷ ( CanBeDuped b depth
    , CanBeDuped a (depth + 1)
    , MinusIsSafe ra rb
    , Equivs depth
    , (ra – rb) ⊆ EvmRange)
  ⇒ StackValue a ra → StackValue b rb
  → EvmBuilder depth (depth + 1) (StackValue depth (ra – rb))
a – b = pushStackValue b ≻≻ pushStackValue a ≻≻ α1 SUB

(÷)
  ∷ ( CanBeDuped b depth
    , CanBeDuped a (depth + 1)
    , Equivs depth
    , NonZero rb
    , (ra ÷ rb) ⊆ EvmRange)
  ⇒ StackValue a ra → StackValue b rb
  → EvmBuilder depth (depth + 1) (StackValue depth (ra ÷ rb))
a ÷ b = pushStackValue b ≻≻ pushStackValue a ≻≻ α1 MOD

require ∷ (Equivs depth) ⇒ EvmBuilder (depth + 1) depth ()
require =
  ignore PC ≻≻
  ignore (PUSH 1 10) ≻≻
  ignore ADD ≻≻
  ignore JUMPI ≻≻
  exitCode (
    ignore (PUSH 1 0) ≻≻
    ignore (PUSH 1 0) ≻≻
    ignore REVERT) ≻≻
  ignore JUMPDEST

boundscheck
  ∷ ( lolo ≤ hihi
    , (lolo :⋯: hihi) ⊆ EvmRange
    , CanBeDuped loSlot depth
    , CanBeDuped valueSlot (depth + 1)
    , CanBeDuped hiSlot (depth + 1)
    , CanBeDuped valueSlot (depth + 2)
    , Equivs depth
    )
  ⇒ StackValue valueSlot range
  → StackValue loSlot (lolo :⋯: lohi)
  → StackValue hiSlot (hilo :⋯: hihi)
  → EvmBuilder depth depth (StackValue valueSlot (lolo :⋯: hihi))
boundscheck val lo hi =
  pushStackValue lo ≻≻
  pushStackValue val ≻≻
  ignore LT ≻≻
  pushStackValue hi ≻≻
  pushStackValue val ≻≻
  ignore GT ≻≻
  ignore OR ≻≻
  ignore ISZERO ≻≻
  require ≻≻
  ret (unsafeCoerce val) -- this is fine


type AccountNumber (r ∷ Range) = r ⊆ (100 :⋯: 104)

getBalance
  ∷ ( AccountNumber accRange
    , CanBeDuped accSlot depth
    , Equivs depth)
  ⇒ StackValue accSlot accRange
  → EvmBuilder depth (depth + 1) (StackValue depth EvmRange)
getBalance acc = pushStackValue acc ≻≻ α1 SLOAD

setBalance
  ∷ ( AccountNumber accRange
    , CanBeDuped valueSlot depth
    , CanBeDuped accSlot (depth + 1)
    , Equivs depth)
  ⇒ StackValue accSlot accRange
  → StackValue valueSlot valueRange
  → EvmBuilder depth depth ()
setBalance acc value = pushStackValue value ≻≻ pushStackValue acc ≻≻ ignore SSTORE

-- <GENERATED CODE>
code = (
  ret ()
  )
-- </GENERATED CODE>

suffix ∷ (Equivs depth) ⇒ EvmBuilder depth depth ()
suffix = ignore (mkPush 0) ≻≻ ignore (mkPush 0) ≻≻ ignore RETURN

constructor ∷ Integer → EvmBuilder 0 0 ()
constructor codeLen =
    ignore (PUSH 4 codeLen) ≻≻
    ignore (PUSH 1 constructorSz) ≻≻
    ignore (PUSH 1 0) ≻≻
    ignore CODECOPY ≻≻
    ignore (PUSH 4 codeLen) ≻≻
    ignore (PUSH 1 0) ≻≻
    ignore RETURN
  where constructorSz = 18

-- Code generation
i2i ∷ (Enum a, Enum b) ⇒ a → b
i2i = toEnum . fromEnum

bigEndian ∷ Integer → Integer → BS.ByteString
bigEndian val len = BS.pack . reverse . map i2i $ bytes len val
  where
    bytes 0 0 = []
    bytes n x = x `mod` 0x100 : bytes (n - 1) (x `div` 0x100)

compileInstr ∷ SomeEvmInstr → BS.ByteString
compileInstr (SomeEvmInstr ins) =
  case ins of
    ADD → "\x01"
    MUL → "\x02"
    SUB → "\x03"
    MOD → "\x06"
    LT → "\x10"
    GT → "\x11"
    ISZERO → "\x15"
    OR → "\x17"
    CODECOPY → "\x39"
    SLOAD → "\x54"
    SSTORE → "\x55"
    JUMP → "\x56"
    JUMPI → "\x57"
    PC → "\x58"
    JUMPDEST → "\x5b"
    PUSH width val → BS.cons (i2i (0x5f + width)) (bigEndian val width)
    (DUP ∷ EvmInstr δ α) →
      let i = natVal (Proxy ∷ Proxy δ)
      in BS.singleton (i2i (0x80 + i))
    RETURN → "\xf3"
    REVERT → "\xfd"

compileEvm ∷ EvmBuilder 0 depth' a → BS.ByteString
compileEvm prog = BS.concat . map compileInstr . F.toList . execEvmBuilder $ prog

main ∷ IO ()
main = BS.putStr (BS.append constructorCode runtimeCode)
  where
    runtimeCode = compileEvm $ code ≻≻ suffix
    constructorCode = compileEvm $ constructor (i2i (BS.length runtimeCode))
