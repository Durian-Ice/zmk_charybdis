{
  description = "Local ZMK firmware build pipeline for Charybdis";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        pythonEnv = pkgs.python3.withPackages (ps: with ps; [ pyyaml ]);
        buildApp = pkgs.writeShellScriptBin "zmk-build" ''
          exec ${./build.sh} "$@"
        '';
      in
      {
        apps = {
          default = {
            type = "app";
            program = "${buildApp}/bin/zmk-build";
          };
          build = {
            type = "app";
            program = "${buildApp}/bin/zmk-build";
          };
        };

        devShells.default = pkgs.mkShell {
          name = "zmk-build-env";
          packages = [
            pythonEnv
            pkgs.docker
            pkgs.git
          ];

          shellHook = ''
            echo "ZMK Local Build Environment"
            echo "Run './build.sh -l' to list available targets."
            echo "Run './build.sh [left|right|reset|all]' to build firmware."
          '';
        };
      }
    );
}
