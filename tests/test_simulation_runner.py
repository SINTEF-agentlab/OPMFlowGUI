"""Tests for the OPM Flow help-text parser in simulation_runner.py."""

from __future__ import annotations

import pytest

from opm_flow_gui.core.simulation_runner import parse_flow_help

# ---------------------------------------------------------------------------
# Sample help text taken directly from an OPM Flow binary
# ---------------------------------------------------------------------------

_SAMPLE_HELP = """\
Recognized options:
    -h,--help                                     Print this help message and exit
    --help-all                                    Print all parameters, including obsolete, hidden and deprecated ones.
    --accelerator-mode=STRING                     Choose a linear solver, usage: '--accelerator-mode=[none|cusparse|opencl|amgcl|rocalution|rocsparse]'. Default: "none"
    --action-parsing-strictness=STRING            Set strictness of parsing process for ActionX and PyAction. Available options are normal (do not apply keywords that have not been tested for ActionX
                                                    or PyAction) and low (try to apply all keywords, beware: the simulation outcome might be incorrect). Default: "normal"
    --add-corners=BOOLEAN                         Add corners to partition. Default: false
    --allow-distributed-wells=BOOLEAN             Allow the perforations of a well to be distributed to interior of multiple processes. Default: false
    --allow-splitting-inactive-wells=BOOLEAN      Allow inactive (never non-shut) wells to be split across multiple domains. Default: true
    --alternative-well-rate-init=BOOLEAN          Use alternative well rate initialization procedure. Default: true
    --convergence-monitoring-cut-off=INTEGER      Cut off limit for convergence monitoring. Default: 6
    --convergence-monitoring-decay-factor=SCALAR  Decay factor for convergence monitoring. Default: 0.75
    --cpr-reuse-interval=INTEGER                  Reuse preconditioner interval. Used when CprReuseSetup is set to 4, then the preconditioner will be fully recreated instead of reused every N linear
                                                    solve, where N is this parameter. Default: 30
    --cpr-reuse-setup=INTEGER                     Reuse preconditioner setup. Valid options are 0: recreate the preconditioner for every linear solve, 1: recreate once every timestep, 2: recreate if
                                                    last linear solve took more than 10 iterations, 3: never recreate, 4: recreated every CprReuseInterval. Default: 4
    --dbhp-max-rel=SCALAR                         Maximum relative change of the bottom-hole pressure in a single iteration. Default: 1
    --debug-verbosity-level=INTEGER               Set debug verbosity level globally. Default is 1, increasing values give additional output and 0 disables most messages to the .DBG file. Default: 1
    --dp-max-rel=SCALAR                           Maximum relative change of pressure in a single iteration. Default: 0.3
    --ds-max=SCALAR                               Maximum absolute change of any saturation in a single iteration. Default: 0.2
    --ecl-deck-file-name=STRING                   The name of the file which contains the ECL deck to be simulated. Default: ""
    --ecl-output-double-precision=BOOLEAN         Tell the output writer to use double precision. Useful for 'perfect' restarts. Default: false
    --ecl-output-interval=INTEGER                 The number of report steps that ought to be skipped between two writes of ECL results. Default: -1
    --enable-adaptive-time-stepping=BOOLEAN       Use adaptive time stepping between report steps. Default: true
    --enable-async-ecl-output=BOOLEAN             Write the ECL-formated results in a non-blocking way (i.e., using a separate thread). Default: true
    --enable-dry-run=STRING                       Specify if the simulation ought to be actually run, or just pretended to be. Default: "auto"
    --enable-ecl-output=BOOLEAN                   Write binary output which is compatible with the commercial Eclipse simulator. Default: true
    --enable-tuning=BOOLEAN                       Honor some aspects of the TUNING keyword. Default: false
    --enable-vtk-output=BOOLEAN                   Global switch for turning on writing VTK files. Default: false
    --linear-solver=STRING                        Configuration of solver. Valid options are: cprw (default), ilu0, dilu, cpr (an alias for cprw), cpr_quasiimpes, cpr_trueimpes,
                                                    cpr_trueimpesanalytic, amg or hybrid (experimental). Alternatively, you can request a configuration to be read from a JSON file by giving the
                                                    filename here, ending with '.json.'. Default: "cprw"
    --linear-solver-max-iter=INTEGER              The maximum number of iterations of the linear solver. Default: 200
    --linear-solver-reduction=SCALAR              The minimum reduction of the residual which the linear solver must achieve. Default: 0.01
    --max-residual-allowed=SCALAR                 Absolute maximum tolerated for residuals without cutting the time step size. Default: 1e+07
    --newton-max-iterations=INTEGER               The maximum number of Newton iterations per time step. Default: 20
    --output-dir=STRING                           The directory to which result files are written. Default: ""
    --output-mode=STRING                          Specify which messages are going to be printed. Valid values are: none, log, all (default). Default: "all"
    --solver-max-time-step-in-days=SCALAR         The maximum size of a time step in days. Default: 365
    --threads-per-process=INTEGER                 The maximum number of threads to be instantiated per process ('-1' means 'automatic'). Default: 2
    --time-step-control=STRING                    The algorithm used to determine time-step sizes. Valid options are: 'pid' (default), 'pid+iteration', 'pid+newtoniteration', 'iterationcount',
                                                    'newtoniterationcount' and 'hardcoded'. Default: "pid+newtoniteration"
    --tolerance-cnv=SCALAR                        Local convergence tolerance (Maximum of local saturation errors). Default: 0.01
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _by_name(options: list[dict], name: str) -> dict:
    """Return the first option descriptor with the given *name*."""
    for opt in options:
        if opt["name"] == name:
            return opt
    raise AssertionError(f"Option '{name}' not found in parsed options")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestParseFlowHelp:
    """Unit tests for :func:`parse_flow_help`."""

    def setup_method(self) -> None:
        self.options = parse_flow_help(_SAMPLE_HELP)

    # -- basic smoke test ---------------------------------------------------

    def test_returns_non_empty_list(self) -> None:
        assert len(self.options) > 0

    def test_all_entries_have_required_keys(self) -> None:
        for opt in self.options:
            for key in ("name", "type", "default", "description"):
                assert key in opt, f"Missing '{key}' in {opt}"

    # -- type mapping -------------------------------------------------------

    def test_boolean_mapped_to_bool(self) -> None:
        opt = _by_name(self.options, "add-corners")
        assert opt["type"] == "bool"

    def test_integer_mapped_to_int(self) -> None:
        opt = _by_name(self.options, "convergence-monitoring-cut-off")
        assert opt["type"] == "int"

    def test_scalar_mapped_to_float(self) -> None:
        opt = _by_name(self.options, "convergence-monitoring-decay-factor")
        assert opt["type"] == "float"

    def test_string_mapped_to_string(self) -> None:
        opt = _by_name(self.options, "accelerator-mode")
        assert opt["type"] == "string"

    # -- default extraction -------------------------------------------------

    def test_boolean_default_false(self) -> None:
        opt = _by_name(self.options, "add-corners")
        assert opt["default"] == "false"

    def test_boolean_default_true(self) -> None:
        opt = _by_name(self.options, "enable-adaptive-time-stepping")
        assert opt["default"] == "true"

    def test_integer_default(self) -> None:
        opt = _by_name(self.options, "convergence-monitoring-cut-off")
        assert opt["default"] == "6"

    def test_negative_integer_default(self) -> None:
        opt = _by_name(self.options, "ecl-output-interval")
        assert opt["default"] == "-1"

    def test_scalar_default(self) -> None:
        opt = _by_name(self.options, "convergence-monitoring-decay-factor")
        assert opt["default"] == "0.75"

    def test_scientific_notation_default(self) -> None:
        opt = _by_name(self.options, "max-residual-allowed")
        assert opt["default"] == "1e+07"

    def test_quoted_string_default_stripped(self) -> None:
        """Surrounding quotes should be removed from string defaults."""
        opt = _by_name(self.options, "accelerator-mode")
        assert opt["default"] == "none"

    def test_empty_string_default(self) -> None:
        opt = _by_name(self.options, "output-dir")
        assert opt["default"] == ""

    def test_large_integer_default(self) -> None:
        opt = _by_name(self.options, "linear-solver-max-iter")
        assert opt["default"] == "200"

    # -- choices extraction -------------------------------------------------

    def test_choices_extracted_for_accelerator_mode(self) -> None:
        opt = _by_name(self.options, "accelerator-mode")
        assert "choices" in opt
        assert "none" in opt["choices"]
        assert "cusparse" in opt["choices"]
        assert "opencl" in opt["choices"]

    def test_no_choices_for_boolean(self) -> None:
        """Boolean options should not have a 'choices' key."""
        opt = _by_name(self.options, "add-corners")
        assert "choices" not in opt

    # -- multiline description handling -------------------------------------

    def test_multiline_description_joined(self) -> None:
        """Continuation lines should be merged into the description."""
        opt = _by_name(self.options, "cpr-reuse-interval")
        assert len(opt["description"]) > 30

    def test_action_parsing_strictness_multiline(self) -> None:
        opt = _by_name(self.options, "action-parsing-strictness")
        assert "ActionX" in opt["description"] or "normal" in opt["description"]

    # -- description does not contain "Default:" --------------------------

    def test_default_removed_from_description(self) -> None:
        for opt in self.options:
            assert "Default:" not in opt["description"], (
                f"'Default:' still present in description of '{opt['name']}'"
            )

    # -- no extra keys for entries without choices -------------------------

    def test_no_spurious_keys(self) -> None:
        opt = _by_name(self.options, "threads-per-process")
        # Only the four mandatory keys plus optional 'choices'
        assert set(opt.keys()) <= {"name", "type", "default", "description", "choices"}

    # -- short-form and non-option lines are ignored -----------------------

    def test_help_short_flag_ignored(self) -> None:
        """The '-h,--help' line does not follow the standard pattern and should be skipped."""
        names = [opt["name"] for opt in self.options]
        assert "h" not in names

    def test_help_all_flag_ignored(self) -> None:
        """'--help-all' has no '=TYPE' and should be skipped."""
        names = [opt["name"] for opt in self.options]
        assert "help-all" not in names
