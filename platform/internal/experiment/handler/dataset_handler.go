// Dataset HTTP handler: user-facing API for managing evaluation datasets and items.
//
// Routes:
//   - POST   /api/v1/experiment/datasets              — Create dataset
//   - GET    /api/v1/experiment/datasets              — List user's datasets
//   - GET    /api/v1/experiment/datasets/{id}         — Get dataset detail
//   - PUT    /api/v1/experiment/datasets/{id}         — Update dataset name/description
//   - POST   /api/v1/experiment/datasets/{id}/items   — Add items (single or batch)
//   - GET    /api/v1/experiment/datasets/{id}/items   — List items (paginated)
//   - DELETE /api/v1/experiment/datasets/{id}/items/{itemId} — Remove item
//   - DELETE /api/v1/experiment/datasets/{id}         — Delete dataset
package handler

import (
	"net/http"
	"strconv"
	"strings"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/experiment/service"
	"deeppool/platform/internal/experiment/types"
)

// DatasetHandler handles dataset-related HTTP requests.
type DatasetHandler struct {
	svc     service.DatasetService
	authSvc types.AuthService
}

// NewDatasetHandler creates a DatasetHandler.
func NewDatasetHandler(svc service.DatasetService, authSvc types.AuthService) *DatasetHandler {
	return &DatasetHandler{svc: svc, authSvc: authSvc}
}

// RegisterRoutes registers dataset routes on the given mux.
func (h *DatasetHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/v1/experiment/datasets", h.handleDatasets)
	mux.HandleFunc("/api/v1/experiment/datasets/", h.handleDatasetByID)
}

// POST/GET /api/v1/experiment/datasets
func (h *DatasetHandler) handleDatasets(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	switch r.Method {
	case http.MethodPost:
		var req types.CreateDatasetRequest
		if err := common.DecodeJSON(r, &req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		dto, err := h.svc.CreateDataset(uid, req)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusCreated, common.Response{Code: 0, Message: "ok", Data: dto})

	case http.MethodGet:
		list, err := h.svc.ListDatasets(uid)
		if err != nil {
			common.WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: list})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

// Routes under /api/v1/experiment/datasets/{id}[/items[/{itemId}]]
func (h *DatasetHandler) handleDatasetByID(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	suffix := strings.TrimPrefix(r.URL.Path, "/api/v1/experiment/datasets/")
	parts := strings.SplitN(suffix, "/", 3) // e.g. ["123"], ["123","items"], ["123","items","456"]
	datasetID, err := strconv.ParseUint(parts[0], 10, 64)
	if err != nil {
		common.WriteError(w, http.StatusBadRequest, "invalid dataset id")
		return
	}

	// Sub-route: /items or /items/{itemId}
	if len(parts) >= 2 && parts[1] == "items" {
		if len(parts) == 3 {
			// DELETE /datasets/{id}/items/{itemId}
			itemID, err := strconv.ParseUint(parts[2], 10, 64)
			if err != nil {
				common.WriteError(w, http.StatusBadRequest, "invalid item id")
				return
			}
			if r.Method != http.MethodDelete {
				common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
				return
			}
			if err := h.svc.RemoveItem(uid, datasetID, itemID); err != nil {
				common.WriteError(w, http.StatusNotFound, err.Error())
				return
			}
			common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})
			return
		}

		// POST /datasets/{id}/items — add items
		// GET  /datasets/{id}/items — list items
		switch r.Method {
		case http.MethodPost:
			var req types.AddDatasetItemsRequest
			if err := common.DecodeJSON(r, &req); err != nil {
				common.WriteError(w, http.StatusBadRequest, err.Error())
				return
			}
			if len(req.Items) == 0 {
				common.WriteError(w, http.StatusBadRequest, "items array is required")
				return
			}
			if err := h.svc.AddItems(uid, datasetID, req.Items); err != nil {
				common.WriteError(w, http.StatusBadRequest, err.Error())
				return
			}
			common.WriteJSON(w, http.StatusCreated, common.Response{Code: 0, Message: "ok"})

		case http.MethodGet:
			q := types.PageQuery{
				Page:     intQuery(r, "page", 1),
				PageSize: intQuery(r, "page_size", 20),
			}
			q.Normalize()
			items, total, err := h.svc.ListItems(datasetID, q.Page, q.PageSize)
			if err != nil {
				common.WriteError(w, http.StatusInternalServerError, err.Error())
				return
			}
			common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: types.PaginatedResponse{Total: total, Items: items}})

		default:
			common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
		}
		return
	}

	// Direct dataset operations
	switch r.Method {
	case http.MethodGet:
		dto, err := h.svc.GetDataset(uid, datasetID)
		if err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: dto})

	case http.MethodPut:
		var req types.UpdateDatasetRequest
		if err := common.DecodeJSON(r, &req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		if err := h.svc.UpdateDataset(uid, datasetID, req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})

	case http.MethodDelete:
		if err := h.svc.DeleteDataset(uid, datasetID); err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (h *DatasetHandler) authUID(w http.ResponseWriter, r *http.Request) (uint64, bool) {
	uid, err := h.authSvc.AuthUserID(r.Header.Get("Authorization"))
	if err != nil {
		common.WriteError(w, http.StatusUnauthorized, "invalid or expired token")
		return 0, false
	}
	return uid, true
}
