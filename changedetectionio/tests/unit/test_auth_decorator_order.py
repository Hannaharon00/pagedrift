"""
Static analysis test: verify @blueprint.route() is always the outermost
decorator on a view, so nothing sits above it.

In Flask, @route() must be outermost because it registers whatever function
it receives and then returns that function unchanged. Any decorator placed
above @route() is applied only to the module-level name, never to the view
the blueprint actually dispatches to — so it is silently dead code. When the
dead decorator is an auth wrapper, the route is left unprotected
(GHSA-jmrh-xmgh-x9j4).

Correct order (route outermost, auth inner):
    @blueprint.route('/path')
    @login_optionally_required
    def view(): ...

Wrong order (auth never called):
    @login_optionally_required   ← discarded; route registered the raw fn
    @blueprint.route('/path')
    def view(): ...

This check is deliberately name-agnostic. An earlier version matched only
the literal name `login_optionally_required`, which missed four routes using
plain flask_login `login_required` (GHSA-q85w-c766-h5g8) — an allowlist of
decorator names only ever catches the names someone remembered to add. We
now flag *any* non-route decorator above @route, which also covers attribute
forms (@flask_login.login_required), aliased imports, and non-auth
decorators that are equally dead up there.

Stacked @route decorators are a legitimate Flask idiom and are exempt.
"""

