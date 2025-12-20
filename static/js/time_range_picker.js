// static/js/time_range_picker.js

// -------- Utility functions --------
function pad2(n) {
  return n < 10 ? "0" + n : "" + n;
}

function formatDate(d) {
  return (
    d.getFullYear() +
    "-" +
    pad2(d.getMonth() + 1) +
    "-" +
    pad2(d.getDate())
  );
}

function formatDateTime(d) {
  return (
    formatDate(d) +
    " " +
    pad2(d.getHours()) +
    ":" +
    pad2(d.getMinutes()) +
    ":" +
    pad2(d.getSeconds())
  );
}

// -------- Quick Ranges: حساب موحّد وصحيح --------
// -------- Quick Ranges: حساب موحّد وصحيح --------
function computeQuickRange(key) {
  // طبع القيمة للتأكد من عدم وجود حروف كبيرة أو مسافات
  key = (key || "").trim().toLowerCase();

  const now = new Date();
  let from = new Date(now);
  let to   = new Date(now);

  switch (key) {
    // ---------------- Day-based named ranges ----------------
    case "today":
      from = new Date(now);
      from.setHours(0, 0, 0, 0);
      to = new Date(now);
      to.setHours(23, 59, 59, 999);
      return [from, to];

    case "yesterday":
      from = new Date(now);
      from.setDate(from.getDate() - 1);
      from.setHours(0, 0, 0, 0);
      to = new Date(from);
      to.setHours(23, 59, 59, 999);
      return [from, to];

    // ندعم الشكلين: this_week و this week فقط للاحتياط
    case "this_week":
    case "this week": {
      // بداية الأسبوع = الإثنين
      let dayOfWeek = now.getDay(); // 0=Sunday, 1=Mon, ...
      if (dayOfWeek === 0) dayOfWeek = 7; // نعتبر الأحد = 7
      from = new Date(now);
      from.setDate(from.getDate() - (dayOfWeek - 1)); // نرجع إلى الإثنين
      from.setHours(0, 0, 0, 0);

      to = new Date(now);
      to.setHours(23, 59, 59, 999);
      return [from, to];
    }

    case "this_month":
    case "this month":
      // من أول يوم في الشهر إلى آخر يوم في نفس الشهر
      from = new Date(now.getFullYear(), now.getMonth(), 1);
      from.setHours(0, 0, 0, 0);

      // اليوم 0 من الشهر التالي = آخر يوم في الشهر الحالي
      to = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      to.setHours(23, 59, 59, 999);

      return [from, to];


    // ---------------- Time-based trailing ranges ----------------
    case "last_12_hours":
      from = new Date(now.getTime() - 12 * 60 * 60 * 1000);
      return [from, to];

    case "last_24_hours":
      from = new Date(now.getTime() - 24 * 60 * 60 * 1000);
      return [from, to];

    case "last_2_days":
      to = new Date(now);
      to.setHours(23, 59, 59, 999);
      from = new Date(now);
      from.setDate(from.getDate() - 1);
      from.setHours(0, 0, 0, 0);
      return [from, to];

    case "last_7_days":
      to = new Date(now);
      to.setHours(23, 59, 59, 999);
      from = new Date(now);
      from.setDate(from.getDate() - 6);
      from.setHours(0, 0, 0, 0);
      return [from, to];

    // ---------------- Default: اليوم الحالي فقط ----------------
    default:
      from = new Date(now);
      from.setHours(0, 0, 0, 0);
      to = new Date(now);
      to.setHours(23, 59, 59, 999);
      return [from, to];
  }
}





// -------- MAIN INIT --------
document.addEventListener("DOMContentLoaded", function () {
  const summaryButton = document.getElementById("timeRangeSummaryButton");
  const summaryLabel = document.getElementById("timeRangeSummaryLabel");
  const panel = document.getElementById("timeRangePanel");
  const overlay = document.getElementById("timeRangeOverlay");
  const closeBtn = document.getElementById("timeRangeCloseButton");
  const fromInput = document.getElementById("timeRangeFromInput");
  const toInput = document.getElementById("timeRangeToInput");
  const applyBtn = document.getElementById("timeRangeApplyButton");
  const hiddenFrom = document.getElementById("dateFromHidden");
  const hiddenTo = document.getElementById("dateToHidden");
  const calendarContainer = document.getElementById("timeRangeCalendar");
  const filtersForm = document.getElementById("filtersForm");

  if (
    !summaryButton ||
    !summaryLabel ||
    !panel ||
    !overlay ||
    !closeBtn ||
    !fromInput ||
    !toInput ||
    !applyBtn ||
    !hiddenFrom ||
    !hiddenTo ||
    !calendarContainer ||
    !filtersForm
  ) {
    return;
  }

  let currentFrom = null;
  let currentTo = null;
  let picker = null;

function initFromHidden() {
    function parseDT(s) {
        // try: YYYY-MM-DD HH:MM:SS
        const dt = new Date(s.replace(" ", "T"));
        if (!isNaN(dt.getTime())) return dt;

        // try: YYYY-MM-DD only → normalize
        const d = new Date(s);
        if (!isNaN(d.getTime())) {
            d.setHours(0,0,0,0);
            return d;
        }
        return null;
    }

    if (hiddenFrom.value) {
        currentFrom = parseDT(hiddenFrom.value);
    }
    if (hiddenTo.value) {
        currentTo = parseDT(hiddenTo.value);
    }

    if (currentFrom && currentTo) {
        fromInput.value = formatDateTime(currentFrom);
        toInput.value   = formatDateTime(currentTo);
        summaryLabel.textContent =
          formatDateTime(currentFrom) + " → " + formatDateTime(currentTo);
    }
}


  initFromHidden();

  // -------- POSITIONING LOGIC (NEW) --------
  function positionPanel() {
    const btnRect = summaryButton.getBoundingClientRect();

    const panelWidth = panel.offsetWidth;
    const panelHeight = panel.offsetHeight;

    let left = window.scrollX + btnRect.left;
    let top = window.scrollY + btnRect.bottom + 8;  // ALWAYS under button

    // prevent overflowing right
    if (left + panelWidth > window.innerWidth - 10) {
        left = window.innerWidth - panelWidth - 10;
    }

    // prevent overflowing bottom
    const maxTop = window.scrollY + window.innerHeight - panelHeight - 10;
    if (top > maxTop) top = maxTop;

    // never less than top = 20
    if (top < 20) top = 20;

    panel.style.left = left + "px";
    panel.style.top = top + "px";
}


  // -------- OPEN PANEL --------
  function openPanel() {
    overlay.classList.remove("hidden");
    panel.classList.remove("hidden");
    panel.classList.add("block");

    positionPanel();

    // Lazy load Litepicker
    if (window.Litepicker && !picker) {
      picker = new Litepicker({
        element: calendarContainer,
        inlineMode: true,
        singleMode: false,
        numberOfMonths: 2,
        numberOfColumns: 2,
        format: "YYYY-MM-DD HH:mm:ss",
        resetButton: true,
        setup: (instance) => {
          if (currentFrom && currentTo) {
            instance.setDateRange(currentFrom, currentTo);
          }
        },
      });

      picker.on("selected", (date1, date2) => {
        if (!date1 || !date2) return;

        currentFrom = date1.dateInstance;
        currentTo = date2.dateInstance;

        // فقط عند اختيار يوم من التقويم → طبّق normalization
        if (date1 && date2) {
            const d1 = date1.dateInstance;
            const d2 = date2.dateInstance;

            // Normalize only for calendar-based selection
            d1.setHours(0,0,0,0);
            d2.setHours(23,59,59,999);

            currentFrom = d1;
            currentTo   = d2;

            fromInput.value = formatDateTime(currentFrom);
            toInput.value   = formatDateTime(currentTo);
        }


        fromInput.value = formatDateTime(currentFrom);
        toInput.value = formatDateTime(currentTo);
      });
    }

    if (picker && currentFrom && currentTo) {
      picker.setDateRange(currentFrom, currentTo);
    }
  }

  // -------- CLOSE PANEL --------
  function closePanel() {
    panel.classList.add("hidden");
    overlay.classList.add("hidden");
  }

  summaryButton.addEventListener("click", openPanel);
  closeBtn.addEventListener("click", closePanel);
  overlay.addEventListener("click", closePanel);

  // -------- QUICK RANGES --------
  const quickButtons = panel.querySelectorAll("[data-quick-range]");
  quickButtons.forEach((btn) => {
    btn.addEventListener("click", function () {
      const key = this.getAttribute("data-quick-range");
      const [from, to] = computeQuickRange(key);
      currentFrom = from;
      currentTo = to;

      fromInput.value = formatDateTime(currentFrom);
      toInput.value = formatDateTime(currentTo);

      if (picker) {
        picker.setDateRange(currentFrom, currentTo);
      }
    });
  });

  // -------- APPLY BUTTON --------
  applyBtn.addEventListener("click", function () {
    if (!fromInput.value || !toInput.value) {
      alert("Please enter valid 'From' and 'To'.");
      return;
    }

    const from = new Date(fromInput.value.replace(" ", "T"));
    const to = new Date(toInput.value.replace(" ", "T"));
    if (isNaN(from.getTime()) || isNaN(to.getTime())) {
      alert("Invalid date/time.");
      return;
    }
    if (from > to) {
      alert("'From' must be before 'To'.");
      return;
    }

    currentFrom = from;
    currentTo = to;

    hiddenFrom.value = formatDateTime(currentFrom);
    hiddenTo.value = formatDateTime(currentTo);

    summaryLabel.textContent =
      hiddenFrom.value + " → " + hiddenTo.value;

    closePanel();

    if (typeof filtersForm.requestSubmit === "function") {
      filtersForm.requestSubmit();
    } else {
      filtersForm.submit();
    }
  });
});
