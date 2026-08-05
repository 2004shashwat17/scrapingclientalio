const apiPrefix = "/api";

async function fetchLeads() {
  const response = await fetch(`${apiPrefix}/leads`);
  return response.json();
}

function setStatus(text) {
  document.getElementById("search-status").textContent = text;
}

function createLeadRow(lead) {
  const template = document.getElementById("lead-row-template").content.cloneNode(true);
  template.querySelector(".lead-name").textContent = lead.CompanyName;
  template.querySelector(".lead-website").textContent = lead.Website;
  template.querySelector(".lead-industry").textContent = lead.Industry || "N/A";
  template.querySelector(".lead-score").textContent = lead.Headquarters || "N/A";
  template.querySelector(".lead-priority").textContent = lead.DecisionMakers || "N/A";
  template.querySelector(".view-btn").addEventListener("click", () => showDetails(lead));
  return template;
}

function showDetails(lead) {
  const content = document.getElementById("detail-content");
  content.innerHTML = `
    <h2>${lead.CompanyName}</h2>
    <p><strong>Website:</strong> <a href="${lead.Website}" target="_blank">${lead.Website}</a></p>
    <p><strong>Headquarters:</strong> ${lead.Headquarters || "N/A"}</p>
    <p><strong>Cities Served:</strong> ${lead.CitiesServed || "N/A"}</p>
    <p><strong>Industry:</strong> ${lead.Industry || "N/A"}</p>
    <p><strong>Fleet Size (if public):</strong> ${lead.FleetSizePublic || "N/A"}</p>
    <p><strong>Employees:</strong> ${lead.Employees || "N/A"}</p>
    <p><strong>Revenue (if public):</strong> ${lead.RevenuePublic || "N/A"}</p>
    <p><strong>Decision Makers:</strong> ${lead.DecisionMakers || "N/A"}</p>
    <p><strong>LinkedIn URL:</strong> ${lead.LinkedInURL || "N/A"}</p>
    <p><strong>Email:</strong> ${lead.Email || "N/A"}</p>
    <p><strong>Phone:</strong> ${lead.Phone || "N/A"}</p>
    <p><strong>CRM/TMS Used (if public):</strong> ${lead.CRMTMSUsedPublic || "N/A"}</p>
    <p><strong>Delivery Volume (if public):</strong> ${lead.DeliveryVolumePublic || "N/A"}</p>
    <p><strong>Existing POD Solution:</strong> ${lead.ExistingPODSolution || "N/A"}</p>
    <p><strong>Notes:</strong> ${lead.Notes || "N/A"}</p>
  `;
  document.getElementById("detail-modal").classList.remove("hidden");
}

async function renderLeads() {
  const list = document.getElementById("lead-list");
  list.innerHTML = "Loading leads...";
  try {
    const leads = await fetchLeads();
    list.innerHTML = "";
    if (!leads.length) {
      list.textContent = "No leads available yet. Execute a search or crawl a website.";
      return;
    }
    leads.forEach((lead) => {
      list.appendChild(createLeadRow(lead));
    });
  } catch (err) {
    list.textContent = "Unable to load leads.";
    console.error(err);
  }
}

async function discoverLeads(event) {
  event.preventDefault();
  const query = document.getElementById("query").value.trim();
  const industry = document.getElementById("industry").value.trim();
  const country = document.getElementById("country").value.trim();
  if (!query) return;

  setStatus("Searching, please wait...");
  try {
    const response = await fetch(`${apiPrefix}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, industry: industry || undefined, country: country || undefined, limit: 200 }),
    });
    const result = await response.json();
    setStatus(`${result.count} leads discovered and saved.`);
    renderLeads();
  } catch (err) {
    setStatus("Search failed. Check server logs.");
    console.error(err);
  }
}

function closeModal() {
  document.getElementById("detail-modal").classList.add("hidden");
}

function exportFile(path) {
  window.location.href = path;
}

function init() {
  document.getElementById("search-form").addEventListener("submit", discoverLeads);
  document.getElementById("refresh-btn").addEventListener("click", renderLeads);
  document.getElementById("export-csv").addEventListener("click", () => exportFile(`${apiPrefix}/export/csv`));
  document.getElementById("export-excel").addEventListener("click", () => exportFile(`${apiPrefix}/export/excel`));
  document.querySelector(".close-btn").addEventListener("click", closeModal);
  document.getElementById("detail-modal").addEventListener("click", (event) => {
    if (event.target.id === "detail-modal") closeModal();
  });
  renderLeads();
}

window.addEventListener("DOMContentLoaded", init);
