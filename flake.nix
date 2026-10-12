{
  description = "Polychromatic built from this checkout";

  inputs.nixpkgs.url = "github:nixos/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      # Swaps the nixpkgs package's source for this checkout, keeping its
      # build and wrapping. Python dependencies resolve from the final package
      # set, so an openrazer override elsewhere in the overlays still applies.
      overlays.default = _: prev: {
        polychromatic = prev.polychromatic.overridePythonAttrs {
          version = "0.9.8+${self.shortRev or self.dirtyShortRev or "dirty"}";
          src = self;
        };
      };

      packages = forAllSystems (pkgs: rec {
        polychromatic = (pkgs.extend self.overlays.default).polychromatic;
        default = polychromatic;
      });
    };
}
