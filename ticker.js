/* PumpReport.news — live price ticker + movers widget
   Pulls real-time spot prices from CoinGecko's public API client-side.
   No hardcoded/fabricated prices anywhere in this file. */
(function () {
  var COINS = [
    { id: "bitcoin", sym: "BTC" },
    { id: "ethereum", sym: "ETH" },
    { id: "solana", sym: "SOL" },
    { id: "dogecoin", sym: "DOGE" },
    { id: "pepe", sym: "PEPE" },
    { id: "bonk", sym: "BONK" },
    { id: "dogwifcoin", sym: "WIF" },
    { id: "pudgy-penguins", sym: "PENGU" }
  ];
  var API =
    "https://api.coingecko.com/api/v3/simple/price?ids=" +
    COINS.map(function (c) { return c.id; }).join(",") +
    "&vs_currencies=usd&include_24hr_change=true";

  function fmtPrice(n) {
    if (n === undefined || n === null) return "—";
    if (n >= 1) return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    if (n >= 0.01) return "$" + n.toFixed(4);
    return "$" + n.toPrecision(3);
  }
  function fmtChg(n) {
    if (n === undefined || n === null) return "";
    var sign = n >= 0 ? "+" : "";
    return sign + n.toFixed(2) + "%";
  }

  function renderTicker(data) {
    var track = document.getElementById("ticker-track");
    if (!track) return;
    var html = "";
    COINS.forEach(function (c) {
      var d = data[c.id];
      if (!d) return;
      var chg = d.usd_24h_change;
      var cls = chg >= 0 ? "up" : "down";
      html +=
        '<span class="ticker-item">' +
        '<span class="sym">' + c.sym + "</span>" +
        '<span class="px">' + fmtPrice(d.usd) + "</span>" +
        '<span class="chg ' + cls + '">' + fmtChg(chg) + "</span>" +
        "</span>";
    });
    // duplicate for seamless scroll on wide tickers
    track.innerHTML = html + html;
  }

  function renderMovers(data) {
    var list = document.getElementById("movers-list");
    if (!list) return;
    var rows = COINS.map(function (c) {
      var d = data[c.id];
      return { sym: c.sym, px: d ? d.usd : null, chg: d ? d.usd_24h_change : null };
    }).filter(function (r) { return r.px !== null; });
    rows.sort(function (a, b) { return (b.chg || 0) - (a.chg || 0); });
    var html = "";
    rows.slice(0, 6).forEach(function (r) {
      var cls = r.chg >= 0 ? "up" : "down";
      html +=
        "<li><span class=\"sym\">" + r.sym + "</span>" +
        "<span class=\"px\">" + fmtPrice(r.px) + "</span>" +
        '<span class="chg ' + cls + '">' + fmtChg(r.chg) + "</span></li>";
    });
    list.innerHTML = html;
  }

  function fallback(msg) {
    var track = document.getElementById("ticker-track");
    if (track) {
      track.innerHTML =
        '<span class="ticker-item">' + msg + "</span>";
    }
    var list = document.getElementById("movers-list");
    if (list) {
      list.innerHTML =
        '<li style="justify-content:center;color:#5b6270;font-family:Barlow,sans-serif;">Live data temporarily unavailable</li>';
    }
  }

  fetch(API)
    .then(function (res) {
      if (!res.ok) throw new Error("bad response");
      return res.json();
    })
    .then(function (data) {
      renderTicker(data);
      renderMovers(data);
    })
    .catch(function () {
      fallback("Live prices unavailable — check CoinGecko or CoinMarketCap directly");
    });
})();
