function monitor() {
  return {
    status: {
      n_done: 0,
      n_success: 0,
      n_failed: 0,
      success_tns: [],
      failure_tns: [],
      progress: 0,
      padding_style: "02d", // fallback
    },
    stats: [],
    hasInitialData: false,
    hasCelebrated: false,

    async init() {
      // listen for data updates from the global store
      window.addEventListener("mojo-data-updated", (e) => {
        this.handleDataUpdate(e.detail);
      });

      // 1. Initial bootstrap
      try {
        const resp = await fetch("/monitor/api/status");
        const data = await resp.json();

        if (data && !data.error) {
          this.handleDataUpdate(data);
          // update global store with the initial pulse
          Alpine.store("dojo").updateSync(Date.now(), data.is_complete);
        }
      } catch (e) {
        console.warn("Monitor bootstrap failed.", e);
      } finally {
        // tell the global store to start the live pulse if needed
        Alpine.store("dojo").startGlobalSync();
        Alpine.store("dojo").setPageReady(true);
      }
    },

    handleDataUpdate(data) {
      this.status = data;
      this.hasInitialData = true;
      this.refreshStats();

      if (this.status.is_complete) {
        this.handleCompletion();
      }
    },

    refreshStats() {
      const totalDone = this.status.n_done || 0;
      const n_trial = this.status.n_trial || 1;
      const progress = ((totalDone / n_trial) * 100).toFixed(1);

      // update tab title with progress
      document.title = `${this.status.is_complete ? "✓" : "(" + progress + "%)"} Monitor | MuJoCo Mojo`;

      const successPerc =
        totalDone > 0
          ? ((this.status.n_success / totalDone) * 100).toFixed(1)
          : 0;
      const failurePerc =
        totalDone > 0
          ? ((this.status.n_failed / totalDone) * 100).toFixed(1)
          : 0;

      const lastSuccess =
        this.status.success_tns.length > 0
          ? this.status.success_tns.slice(-1)[0]
          : "None";
      const lastFailure =
        this.status.failure_tns.length > 0
          ? this.status.failure_tns.slice(-1)[0]
          : "None";

      this.stats = [
        {
          label: "Successes",
          value: `${this.status.n_success} (${successPerc}%)`,
          color: "text-emerald-500",
          subValue: `Last Success: Trial ${lastSuccess}`,
        },
        {
          label: "Failures",
          value: `${this.status.n_failed} (${failurePerc}%)`,
          color: "text-rose-500",
          subValue: `Last Failure: Trial ${lastFailure}`,
        },
        {
          label: "Remaining",
          value: `${this.status.n_remaining} (${(100 - progress).toFixed(1)}%)`,
          color: "text-amber-500",
          subValue: `${this.status.throughput} trials/min (${this.status.avg_duration} per trial)`,
        },
        {
          label: "Time Elapsed",
          value: this.status.elapsed,
          color: "text-slate-500",
          subValue: `Started: ${this.status.start_time}`,
        },
        {
          label: "Total Done",
          value: `${totalDone}`,
          color: "text-cyan-500",
          subValue: `Target: ${n_trial} trials`,
        },
        {
          label: this.status.is_complete ? "Finished" : "Est. Remaining",
          value: this.status.is_complete
            ? "00:00:00"
            : this.status.time_remaining,
          color: "text-slate-500",
          subValue: this.status.is_complete
            ? "Job Complete"
            : `ETA: ${this.status.end_time}`,
        },
      ];
    },

    handleCompletion() {
      // Check the local variable instead of sessionStorage
      if (this.hasCelebrated) return;

      const theme = this.getHolidayTheme();
      const chime = document.getElementById("chime");

      if (!Alpine.store("dojo").isMuted) {
        if (theme.audioUrl) {
          const holidaySound = new Audio(theme.audioUrl);
          holidaySound.play().catch(() => chime.play().catch(() => {}));
        } else {
          chime.play().catch(() => {});
        }
      }

      this.fireConfetti(theme);

      // Mark as celebrated so it doesn't fire again until the next refresh
      this.hasCelebrated = true;
    },

    getHolidayTheme() {
      const now = new Date();
      // const m = now.getMonth(); // 0-11
      // const d = now.getDate();
      const m = 2; // 0-11
      const d = 17;

      // New Year
      if ((m === 11 && d === 31) || (m === 0 && d <= 2)) {
        return {
          name: "New Year",
          emojis: ["🎆", "✨", "🥂"],
          colors: ["#ffcc00", "#ffffff"],
          audioUrl:
            "https://actions.google.com/sounds/v1/human_voices/crowd_cheer.ogg", // TODO
        };
      }
      // Pi Day
      if (m === 2 && d === 14) {
        return {
          name: "Pi Day",
          emojis: ["π", "🥧"],
          colors: ["#ff9900"],
          audioUrl:
            "https://actions.google.com/sounds/v1/science_fiction/sci_fi_pulse.ogg", // TODO
        };
      }
      // St. Patrick's
      if (m === 2 && d === 17) {
        return {
          name: "St. Patrick's Day",
          emojis: ["🍀", "🌈"],
          colors: ["#22c55e", "#166534"],
          audioUrl:
            "https://actions.google.com/sounds/v1/foley/wind_chime_vibrant.ogg", // TODO
        };
      }
      // May the 4th
      if (m === 4 && d === 4) {
        return {
          name: "May the 4th",
          emojis: ["⚔️", "🌌", "✨"],
          colors: ["#FFE81F", "#2dd4bf"],
          audioUrl:
            "https://actions.google.com/sounds/v1/science_fiction/laser_burst.ogg", // TODO
        };
      }
      // Halloween
      if ((m === 9 && d >= 25) || (m === 10 && d === 1)) {
        return {
          name: "Halloween",
          emojis: ["🎃", "👻", "🦇"],
          colors: ["#ff6600", "#9437ff"],
          audioUrl:
            "https://actions.google.com/sounds/v1/horror/ghost_ly_laugh.ogg", // TODO
        };
      }
      // Winter/Snow
      if (m === 11 || (m === 0 && d <= 15)) {
        return {
          name: "Winter Snow",
          emojis: ["❄️", "⛄", "🌨️"],
          isSnow: true,
          audioUrl:
            "https://actions.google.com/sounds/v1/foley/sleigh_bells_ring.ogg", // TODO
        };
      }

      return {
        name: "Standard Mojo",
        colors: ["#06b6d4", "#3b82f6", "#22c55e"],
        // No audioUrl, defaults to chime
      };
    },

    fireConfetti(theme = {}) {
      const themeName = theme.name || "Standard Mojo";
      const isSpecial = !!theme.emojis;
      const isSnow = theme.isSnow || false;

      console.log(
        `%c 🎊 Mojo Celebration: ${themeName} `,
        "background: #06b6d4; color: #fff; font-weight: bold; padding: 2px 4px; border-radius: 4px;",
      );

      const duration = 3000;
      const animationEnd = Date.now() + duration;
      const colors = theme.colors || ["#06b6d4", "#3b82f6", "#22c55e"];

      // 1. Shapes + Color Fix (Pi will now be Orange, not Black)
      let shapes = ["circle", "square"];
      if (theme.emojis) {
        shapes = theme.emojis.map((emoji) =>
          confetti.shapeFromText({
            text: emoji,
            scalar: 5,
            color: colors[0], // Forces the symbol to use the theme color
          }),
        );
      }

      // 2. Physics Profiles
      const defaults = {
        zIndex: 1000,
        shapes: shapes,
        colors: colors,
        ticks: isSpecial ? 200 : 100,
        scalar: isSpecial ? 5 : 1,
        // Lower gravity (0.4) makes the rotation much slower and floatier
        gravity: isSnow ? 0.4 : isSpecial ? 0.4 : 1.2,
      };

      const interval = setInterval(
        () => {
          const timeLeft = animationEnd - Date.now();
          if (timeLeft <= 0) return clearInterval(interval);

          if (isSnow) {
            confetti({
              ...defaults,
              particleCount: 1,
              startVelocity: 0,
              drift: (Math.random() - 0.5) * 1.5,
              origin: { x: Math.random(), y: -0.2 },
            });
          } else {
            // 3. BOOSTED DENSITY & CENTER COVERAGE
            // We increased standard from 50 to 150 particles per tick
            const countMultiplier = isSpecial ? 40 : 150;
            const particleCount = countMultiplier * (timeLeft / duration);

            // Triple-pop: Fire 3 random bursts every interval to saturate the screen
            for (let i = 0; i < 3; i++) {
              confetti({
                ...defaults,
                particleCount: Math.ceil(particleCount / 3),
                spread: isSpecial ? 90 : 360,
                // Slower velocity (15) for special items makes them easier to read
                startVelocity: isSpecial ? 15 : 45,
                origin: {
                  x: Math.random(), // FILL THE CENTER: Completely random horizontal
                  y: Math.random() - 0.2, // Random vertical
                },
              });
            }
          }
        },
        isSpecial ? 400 : 250,
      );
    },
  };
}
