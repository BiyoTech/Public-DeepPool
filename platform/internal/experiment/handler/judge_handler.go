// Judge HTTP handler: direct HTTP handler for experiment server (non-gRPC path).
// Note: In the standard architecture, all requests go through Manager → gRPC.
// This handler is kept for standalone testing / direct experiment server access.
package handler

import (
	"net/http"
	"strconv"
	"strings"

	"deeppool/platform/internal/common"
	"deeppool/platform/internal/experiment/service"
	"deeppool/platform/internal/experiment/types"
)

// JudgeHandler handles judge-related HTTP requests.
type JudgeHandler struct {
	svc     service.JudgeService
	authSvc types.AuthService
}

// NewJudgeHandler creates a JudgeHandler.
func NewJudgeHandler(svc service.JudgeService, authSvc types.AuthService) *JudgeHandler {
	return &JudgeHandler{svc: svc, authSvc: authSvc}
}

// RegisterRoutes registers judge routes on the given mux.
func (h *JudgeHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/v1/experiment/judges", h.handleJudges)
	mux.HandleFunc("/api/v1/experiment/judges/", h.handleJudgeByID)
	mux.HandleFunc("/api/v1/experiment/scorers", h.handleBuiltinScorers)
}

// POST/GET /api/v1/experiment/judges
func (h *JudgeHandler) handleJudges(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	switch r.Method {
	case http.MethodPost:
		var req types.CreateJudgeRequest
		if err := common.DecodeJSON(r, &req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		dto, err := h.svc.CreateJudge(uid, req)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusCreated, common.Response{Code: 0, Message: "ok", Data: dto})

	case http.MethodGet:
		list, err := h.svc.ListJudges(uid)
		if err != nil {
			common.WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: list})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

// Routes under /api/v1/experiment/judges/{id}[/run|/runs[/{runId}/results]]
func (h *JudgeHandler) handleJudgeByID(w http.ResponseWriter, r *http.Request) {
	uid, ok := h.authUID(w, r)
	if !ok {
		return
	}

	suffix := strings.TrimPrefix(r.URL.Path, "/api/v1/experiment/judges/")
	parts := strings.SplitN(suffix, "/", 4)
	judgeID, err := strconv.ParseUint(parts[0], 10, 64)
	if err != nil {
		common.WriteError(w, http.StatusBadRequest, "invalid judge id")
		return
	}

	subPath := ""
	if len(parts) > 1 {
		subPath = parts[1]
	}

	switch {
	// POST /judges/{id}/run — start a new run
	case subPath == "run" && r.Method == http.MethodPost:
		run, err := h.svc.RunJudge(uid, judgeID)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: run})

	// GET /judges/{id}/runs — list runs
	case subPath == "runs" && len(parts) == 2 && r.Method == http.MethodGet:
		runs, err := h.svc.ListJudgeRuns(judgeID)
		if err != nil {
			common.WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: runs})

	// GET /judges/{id}/runs/{runId}/results — run results
	case subPath == "runs" && len(parts) == 4 && parts[3] == "results" && r.Method == http.MethodGet:
		runID, err := strconv.ParseUint(parts[2], 10, 64)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, "invalid run id")
			return
		}
		q := types.PageQuery{
			Page:     intQuery(r, "page", 1),
			PageSize: intQuery(r, "page_size", 20),
		}
		q.Normalize()
		results, hasMore, err := h.svc.GetJudgeRunResults(runID, q.Page, q.PageSize)
		if err != nil {
			common.WriteError(w, http.StatusInternalServerError, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: map[string]interface{}{"items": results, "has_more": hasMore}})

	// GET /judges/{id} — get detail
	case subPath == "" && r.Method == http.MethodGet:
		dto, err := h.svc.GetJudge(uid, judgeID)
		if err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: dto})

	// PUT /judges/{id} — update config
	case subPath == "" && r.Method == http.MethodPut:
		var req types.UpdateJudgeRequest
		if err := common.DecodeJSON(r, &req); err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		dto, err := h.svc.UpdateJudge(uid, judgeID, req)
		if err != nil {
			common.WriteError(w, http.StatusBadRequest, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: dto})

	// DELETE /judges/{id} — delete
	case subPath == "" && r.Method == http.MethodDelete:
		if err := h.svc.DeleteJudge(uid, judgeID); err != nil {
			common.WriteError(w, http.StatusNotFound, err.Error())
			return
		}
		common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok"})

	default:
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
	}
}

// GET /api/v1/experiment/scorers
func (h *JudgeHandler) handleBuiltinScorers(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		common.WriteError(w, http.StatusMethodNotAllowed, "method not allowed")
		return
	}
	lang := r.URL.Query().Get("lang")
	scorers := h.svc.ListBuiltinScorers(lang)
	common.WriteJSON(w, http.StatusOK, common.Response{Code: 0, Message: "ok", Data: scorers})
}

func (h *JudgeHandler) authUID(w http.ResponseWriter, r *http.Request) (uint64, bool) {
	uid, err := h.authSvc.AuthUserID(r.Header.Get("Authorization"))
	if err != nil {
		common.WriteError(w, http.StatusUnauthorized, "invalid or expired token")
		return 0, false
	}
	return uid, true
}
