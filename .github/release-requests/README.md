# Authorized release requests

This directory is a developer-only audit surface for release publication.

A file named `vX.Y.Z` is a deliberate release authorization. Merging that marker to `main` causes the authorization workflow to:

1. wait for Quality to pass at that exact main commit (fail closed otherwise);
2. confirm the marker matches the package version;
3. verify version synchronization and public release notes;
4. create the immutable annotated Git tag at the exact merge commit; and
5. dispatch the existing multi-platform release workflow from that tag.

Do not add or edit a marker until the release candidate has passed review and all required checks. Published tags are never moved or rewritten. A failed published release is corrected in a new patch version.
