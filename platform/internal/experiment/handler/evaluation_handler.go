// Evaluation HTTP handler: user-facing API for creating, running, and querying evaluations.
//
// Routes:
//   - POST   /api/v1/experiment/evaluations            — Create evaluation
//   - GET    /api/v1/experiment/evaluations            — List user's evaluations
//   - GET    /api/v1/experiment/evaluations/{id}       — Get evaluation detail
//   - POST   /api/v1/experiment/evaluations/{id}/run   — Start evaluation execution
//   - GET    /api/v1/experiment/evaluations/{id}/results — List evaluation results
//   - DELETE /api/v1/experiment/evaluations/{id}       — Delete evaluation
package handler

import (
	"net/http"
	"strconv"
	"strings"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/experiment/service"
	"deeppool/platform/internal/experiment/types"
)

// EvaluationHandler handles evaluation-related HTTP requests.
type EvaluationHandler struct {
	svc     service.EvaluationService
	authSvc types.AuthService
}

// NewEvaluationHandler creates an EvaluationHandler.
func NewEvaluationHandler(svc service.EvaluationService, authSvc types.AuthService) *EvaluationHandler {
	return &EvaluationHandler{svc: svc, authSvc: authSvc}
}

// RegisterRoutes registers evaluation routes on the given mux.
func (h *EvaluationHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/v1/experiment/evaluations", h.handleEvaluations)
	mux.HandleFunc("/api/v1/experiment/evaluations/", h.handleEvaluationByID)
}

// POST/GET /api/v1/experiment/evaluations
func (h *EvaluationHandler) handleEvaluations(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	switch r.Method {
	case http.MethodPost:
		var req types.CreateEvaluationRequest
		if err := common.DecodeJSON(r, &req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		dto, err := h.svc.CreateEvaluation(uid, req)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusCreated, common.Response{Code: 0, Message: "ok", Data: dto})

	case http.MethodGet:
		list, err := h.svc.ListEvaluations(uid)
		if err != nil {
			common.WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: list})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

// Routes under /api/v1/experiment/evaluations/{id}[/run|/results]
func (h *EvaluationHandler) handleEvaluationByID(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	suffix := strings.TrimPrefix(r.URL.Path, "/api/v1/experiment/evaluations/")
	parts := strings.SplitN(suffix, "/", 2)
	evalID, err := strconv.ParseUint(parts[0], 10, 64)
	if err != nil {
		common.WriteError(w, http.StatusBadRequest, "invalid evaluation id")
		return
	}

	// Sub-routes
	if len(parts) == 2 {
		switch parts[1] {
		case "run":
			if r.Method != http.MethodPost {
				common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
				return
			}
			if err := h.svc.RunEvaluation(uid, evalID); err != nil {
				common.WriteError(w, http.StatusBadRequest, err.Error())
				return
			}
			common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})
			return

		case "results":
			if r.Method != http.MethodGet {
				common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
				return
			}
			q := types.PageQuery{
				Page:     intQuery(r, "page", 1),
				PageSize: intQuery(r, "page_size", 20),
			}
			q.Normalize()
			results, total, err := h.svc.GetEvaluationResults(evalID, q.Page, q.PageSize)
			if err != nil {
				common.WriteError(w, http.StatusInternalServerError, err.Error())
				return
			}
			common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: types.PaginatedResponse{Total: total, Items: results}})
			return
		}
	}

	// Direct evaluation operations
	switch r.Method {
	case http.MethodGet:
		dto, err := h.svc.GetEvaluation(uid, evalID)
		if err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: dto})

	case http.MethodDelete:
		if err := h.svc.DeleteEvaluation(uid, evalID); err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

func (h *EvaluationHandler) authUID(w http.ResponseWriter, r *http.Request) (uint64, bool) {
	uid, err := h.authSvc.AuthUserID(r.Header.Get("Authorization"))
	if err != nil {
		common.WriteError(w, http.StatusUnauthorized, "invalid or expired token")
		return 0, false
	}
	return uid, true
}
