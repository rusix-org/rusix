# VMA merge source checkpoint

Seventeen complete merge/expand/shrink policies (708 Rust lines), six native
entry wrappers, 42 new field/operation primitives and 31 reused functions.
The source snapshots bind exactly nine files. Independent review and whole-file
C restoration pass; all 17 native bodies match the pinned reference. Constants
are recorded separately (six new, two reused).

Author and independent records retain their original pre-link PROGRESS identity;
source-identities.json binds the final link and header-whitespace updates. The scout
is referenced by base commit, input hashes and original manifest hash; only its
short report and input inventory are copied. No older evidence tree is embedded.
Author checkpatch.log preserves the initial malformed-SPDX warnings; the corrected
headers pass checkpatch-final.log and the new captured final checks. These style
checks cover the two new C headers. Formatting and whitespace checks are distinct
from compiler validation. The archived restoration check is textual selector
projection, never actual preprocessor output.

This checkpoint establishes source translation/review only. Configuration,
compiler/typecheck, object/archive/linked selection and paired VM tests remain
pending, including the modification prerequisite. Native primitives still execute
C; no subsystem divergence or full compatibility is claimed.

Staging exposed one trailing blank line in the previously untracked native header;
it was removed. The retained staged-check failure and final source identities
distinguish that whitespace change from the reviewed function bodies.
