// gRPC service implementation: bridges proto ExperimentService to internal service layer.
package experiment

import (
	"context"
	"log"

	experimentv1 "deeppool/libs/proto/experiment/v1"
	"deeppool/platform/internal/experiment/service"
	"deeppool/platform/internal/experiment/types"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// GRPCService implements experimentv1.ExperimentServiceServer.
type GRPCService struct {
	experimentv1.UnimplementedExperimentServiceServer
	judgeSvc      service.JudgeService
	datasetSvc    service.DatasetService
	evalSvc       service.EvaluationService
	annotationSvc service.AnnotationService
}

// NewGRPCService creates the gRPC service implementation.
func NewGRPCService(judgeSvc service.JudgeService, datasetSvc service.DatasetService, evalSvc service.EvaluationService, annotationSvc service.AnnotationService) *GRPCService {
	return &GRPCService{judgeSvc: judgeSvc, datasetSvc: datasetSvc, evalSvc: evalSvc, annotationSvc: annotationSvc}
}

// --- Health ---

func (s *GRPCService) Health(ctx context.Context, req *experimentv1.HealthRequest) (*experimentv1.HealthResponse, error) {
	return &experimentv1.HealthResponse{Status: "ok", Service: "experiment"}, nil
}

// --- Judge ---

func (s *GRPCService) CreateJudge(ctx context.Context, req *experimentv1.CreateJudgeRequest) (*experimentv1.JudgeResponse, error) {
	dto, err := s.judgeSvc.CreateJudge(req.UserId, types.CreateJudgeRequest{
		Name:           req.Name,
		Scope:          req.Scope,
		ScopeValue:     req.ScopeValue,
		TraceID:        req.TraceId,
		JudgeModel:     req.JudgeModel,
		JudgeAPIKeyID:  req.JudgeApikeyId,
		ScorerType:     req.ScorerType,
		ScorerName:     req.ScorerName,
		PromptTemplate: req.PromptTemplate,
	})
	if err != nil {
		log.Printf("[ERROR] grpc_service: CreateJudge failed uid=%d name=%s: %v", req.UserId, req.Name, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.JudgeResponse{Judge: judgeToProto(dto)}, nil
}

func (s *GRPCService) UpdateJudge(ctx context.Context, req *experimentv1.UpdateJudgeRequest) (*experimentv1.JudgeResponse, error) {
	updateReq := types.UpdateJudgeRequest{}
	if req.Name != nil {
		updateReq.Name = req.Name
	}
	if req.Scope != nil {
		updateReq.Scope = req.Scope
	}
	if req.ScopeValue != nil {
		updateReq.ScopeValue = req.ScopeValue
	}
	if req.TraceId != nil {
		updateReq.TraceID = req.TraceId
	}
	if req.JudgeModel != nil {
		updateReq.JudgeModel = req.JudgeModel
	}
	if req.JudgeApikeyId != nil {
		updateReq.JudgeAPIKeyID = req.JudgeApikeyId
	}
	if req.ScorerType != nil {
		updateReq.ScorerType = req.ScorerType
	}
	if req.ScorerName != nil {
		updateReq.ScorerName = req.ScorerName
	}
	if req.PromptTemplate != nil {
		updateReq.PromptTemplate = req.PromptTemplate
	}

	dto, err := s.judgeSvc.UpdateJudge(req.UserId, req.JudgeId, updateReq)
	if err != nil {
		log.Printf("[ERROR] grpc_service: UpdateJudge failed uid=%d judge_id=%d: %v", req.UserId, req.JudgeId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.JudgeResponse{Judge: judgeToProto(dto)}, nil
}

func (s *GRPCService) GetJudge(ctx context.Context, req *experimentv1.GetJudgeRequest) (*experimentv1.JudgeResponse, error) {
	dto, err := s.judgeSvc.GetJudge(req.UserId, req.JudgeId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetJudge failed uid=%d judge_id=%d: %v", req.UserId, req.JudgeId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.JudgeResponse{Judge: judgeToProto(dto)}, nil
}

func (s *GRPCService) ListJudges(ctx context.Context, req *experimentv1.ListJudgesRequest) (*experimentv1.ListJudgesResponse, error) {
	list, err := s.judgeSvc.ListJudges(req.UserId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: ListJudges failed uid=%d: %v", req.UserId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.ListJudgesResponse{}
	for i := range list {
		resp.Judges = append(resp.Judges, judgeToProto(&list[i]))
	}
	return resp, nil
}

func (s *GRPCService) RunJudge(ctx context.Context, req *experimentv1.RunJudgeRequest) (*experimentv1.RunJudgeResponse, error) {
	run, err := s.judgeSvc.RunJudge(req.UserId, req.JudgeId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: RunJudge failed uid=%d judge_id=%d: %v", req.UserId, req.JudgeId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.RunJudgeResponse{Ok: true, Run: judgeRunToProto(run)}, nil
}

func (s *GRPCService) ListJudgeRuns(ctx context.Context, req *experimentv1.ListJudgeRunsRequest) (*experimentv1.ListJudgeRunsResponse, error) {
	runs, err := s.judgeSvc.ListJudgeRuns(req.JudgeId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: ListJudgeRuns failed judge_id=%d: %v", req.JudgeId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.ListJudgeRunsResponse{}
	for i := range runs {
		resp.Runs = append(resp.Runs, judgeRunToProto(&runs[i]))
	}
	return resp, nil
}

func (s *GRPCService) GetJudgeRunResults(ctx context.Context, req *experimentv1.GetJudgeRunResultsRequest) (*experimentv1.GetJudgeRunResultsResponse, error) {
	results, hasMore, err := s.judgeSvc.GetJudgeRunResults(req.RunId, int(req.Page), int(req.PageSize))
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetJudgeRunResults failed run_id=%d: %v", req.RunId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.GetJudgeRunResultsResponse{HasMore: hasMore}
	for _, r := range results {
		resp.Results = append(resp.Results, judgeResultToProto(&r))
	}
	return resp, nil
}

func (s *GRPCService) DeleteJudge(ctx context.Context, req *experimentv1.DeleteJudgeRequest) (*experimentv1.DeleteJudgeResponse, error) {
	if err := s.judgeSvc.DeleteJudge(req.UserId, req.JudgeId); err != nil {
		log.Printf("[ERROR] grpc_service: DeleteJudge failed uid=%d judge_id=%d: %v", req.UserId, req.JudgeId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DeleteJudgeResponse{Ok: true}, nil
}

func (s *GRPCService) ListBuiltinScorers(ctx context.Context, req *experimentv1.ListBuiltinScorersRequest) (*experimentv1.ListBuiltinScorersResponse, error) {
	scorers := s.judgeSvc.ListBuiltinScorers(req.Lang)
	resp := &experimentv1.ListBuiltinScorersResponse{}
	for _, sc := range scorers {
		resp.Scorers = append(resp.Scorers, &experimentv1.BuiltinScorerDTO{
			Name:           sc.Name,
			DisplayName:    sc.DisplayName,
			Description:    sc.Description,
			PromptTemplate: sc.PromptTemplate,
		})
	}
	return resp, nil
}

// --- Dataset ---

func (s *GRPCService) CreateDataset(ctx context.Context, req *experimentv1.CreateDatasetRequest) (*experimentv1.DatasetResponse, error) {
	dto, err := s.datasetSvc.CreateDataset(req.UserId, types.CreateDatasetRequest{
		Name:        req.Name,
		Description: req.Description,
	})
	if err != nil {
		log.Printf("[ERROR] grpc_service: CreateDataset failed uid=%d: %v", req.UserId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DatasetResponse{Dataset: datasetToProto(dto)}, nil
}

func (s *GRPCService) GetDataset(ctx context.Context, req *experimentv1.GetDatasetRequest) (*experimentv1.DatasetResponse, error) {
	dto, err := s.datasetSvc.GetDataset(req.UserId, req.DatasetId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetDataset failed uid=%d dataset_id=%d: %v", req.UserId, req.DatasetId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DatasetResponse{Dataset: datasetToProto(dto)}, nil
}

func (s *GRPCService) ListDatasets(ctx context.Context, req *experimentv1.ListDatasetsRequest) (*experimentv1.ListDatasetsResponse, error) {
	list, err := s.datasetSvc.ListDatasets(req.UserId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: ListDatasets failed uid=%d: %v", req.UserId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.ListDatasetsResponse{}
	for i := range list {
		resp.Datasets = append(resp.Datasets, datasetToProto(&list[i]))
	}
	return resp, nil
}

func (s *GRPCService) AddDatasetItems(ctx context.Context, req *experimentv1.AddDatasetItemsRequest) (*experimentv1.AddDatasetItemsResponse, error) {
	items := make([]types.AddDatasetItemRequest, 0, len(req.Items))
	for _, it := range req.Items {
		items = append(items, types.AddDatasetItemRequest{
			Input:          it.Input,
			ExpectedOutput: it.ExpectedOutput,
			Metadata:       it.Metadata,
		})
	}
	if err := s.datasetSvc.AddItems(req.UserId, req.DatasetId, items); err != nil {
		log.Printf("[ERROR] grpc_service: AddDatasetItems failed uid=%d dataset_id=%d: %v", req.UserId, req.DatasetId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.AddDatasetItemsResponse{AddedCount: int32(len(items))}, nil
}

func (s *GRPCService) DeleteDatasetItem(ctx context.Context, req *experimentv1.DeleteDatasetItemRequest) (*experimentv1.DeleteDatasetItemResponse, error) {
	if err := s.datasetSvc.RemoveItem(req.UserId, req.DatasetId, req.ItemId); err != nil {
		log.Printf("[ERROR] grpc_service: DeleteDatasetItem failed uid=%d dataset_id=%d item_id=%d: %v", req.UserId, req.DatasetId, req.ItemId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DeleteDatasetItemResponse{Ok: true}, nil
}

func (s *GRPCService) DeleteDataset(ctx context.Context, req *experimentv1.DeleteDatasetRequest) (*experimentv1.DeleteDatasetResponse, error) {
	if err := s.datasetSvc.DeleteDataset(req.UserId, req.DatasetId); err != nil {
		log.Printf("[ERROR] grpc_service: DeleteDataset failed uid=%d dataset_id=%d: %v", req.UserId, req.DatasetId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DeleteDatasetResponse{Ok: true}, nil
}

// --- Evaluation ---

func (s *GRPCService) CreateEvaluation(ctx context.Context, req *experimentv1.CreateEvaluationRequest) (*experimentv1.EvaluationResponse, error) {
	dto, err := s.evalSvc.CreateEvaluation(req.UserId, types.CreateEvaluationRequest{
		Name:      req.Name,
		DatasetID: req.DatasetId,
		ModelName: req.ModelName,
		APIKeyID:  req.ApikeyId,
	})
	if err != nil {
		log.Printf("[ERROR] grpc_service: CreateEvaluation failed uid=%d: %v", req.UserId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.EvaluationResponse{Evaluation: evaluationToProto(dto)}, nil
}

func (s *GRPCService) GetEvaluation(ctx context.Context, req *experimentv1.GetEvaluationRequest) (*experimentv1.EvaluationResponse, error) {
	dto, err := s.evalSvc.GetEvaluation(req.UserId, req.EvaluationId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetEvaluation failed uid=%d eval_id=%d: %v", req.UserId, req.EvaluationId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.EvaluationResponse{Evaluation: evaluationToProto(dto)}, nil
}

func (s *GRPCService) ListEvaluations(ctx context.Context, req *experimentv1.ListEvaluationsRequest) (*experimentv1.ListEvaluationsResponse, error) {
	list, err := s.evalSvc.ListEvaluations(req.UserId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: ListEvaluations failed uid=%d: %v", req.UserId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.ListEvaluationsResponse{}
	for i := range list {
		resp.Evaluations = append(resp.Evaluations, evaluationToProto(&list[i]))
	}
	return resp, nil
}

func (s *GRPCService) RunEvaluation(ctx context.Context, req *experimentv1.RunEvaluationRequest) (*experimentv1.RunEvaluationResponse, error) {
	if err := s.evalSvc.RunEvaluation(req.UserId, req.EvaluationId); err != nil {
		log.Printf("[ERROR] grpc_service: RunEvaluation failed uid=%d eval_id=%d: %v", req.UserId, req.EvaluationId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.RunEvaluationResponse{Ok: true}, nil
}

func (s *GRPCService) GetEvaluationResults(ctx context.Context, req *experimentv1.GetEvaluationResultsRequest) (*experimentv1.GetEvaluationResultsResponse, error) {
	results, total, err := s.evalSvc.GetEvaluationResults(req.EvaluationId, int(req.Page), int(req.PageSize))
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetEvaluationResults failed eval_id=%d: %v", req.EvaluationId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	resp := &experimentv1.GetEvaluationResultsResponse{Total: total}
	for _, r := range results {
		resp.Results = append(resp.Results, evalResultToProto(&r))
	}
	return resp, nil
}

func (s *GRPCService) DeleteEvaluation(ctx context.Context, req *experimentv1.DeleteEvaluationRequest) (*experimentv1.DeleteEvaluationResponse, error) {
	if err := s.evalSvc.DeleteEvaluation(req.UserId, req.EvaluationId); err != nil {
		log.Printf("[ERROR] grpc_service: DeleteEvaluation failed uid=%d eval_id=%d: %v", req.UserId, req.EvaluationId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.DeleteEvaluationResponse{Ok: true}, nil
}

// --- Proto conversion helpers ---

func judgeToProto(d *types.JudgeDTO) *experimentv1.JudgeDTO {
	if d == nil {
		return nil
	}
	return &experimentv1.JudgeDTO{
		Id:             d.ID,
		UserId:         d.UserID,
		Name:           d.Name,
		Scope:          d.Scope,
		ScopeValue:     d.ScopeValue,
		TraceId:        d.TraceID,
		JudgeModel:     d.JudgeModel,
		JudgeApikeyId:  d.JudgeAPIKeyID,
		ScorerType:     d.ScorerType,
		ScorerName:     d.ScorerName,
		PromptTemplate: d.PromptTemplate,
		Status:         d.Status,
		TotalCount:     int32(d.TotalCount),
		CompletedCount: int32(d.CompletedCount),
		FailedCount:    int32(d.FailedCount),
		CreatedAt:      d.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
		UpdatedAt:      d.UpdatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

func judgeResultToProto(r *types.JudgeResultDTO) *experimentv1.JudgeResultDTO {
	return &experimentv1.JudgeResultDTO{
		Id:           r.ID,
		RunId:        r.RunID,
		JudgeId:      r.JudgeID,
		TraceLogId:   r.TraceLogID,
		RequestId:    r.RequestID,
		Passed:       r.Passed,
		Reason:       r.Reason,
		RawOutput:    r.RawOutput,
		DurationMs:   r.DurationMs,
		Success:      r.Success,
		ErrorMessage: r.ErrorMessage,
		CreatedAt:    r.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

func judgeRunToProto(r *types.JudgeRunDTO) *experimentv1.JudgeRunDTO {
	if r == nil {
		return nil
	}
	return &experimentv1.JudgeRunDTO{
		Id:             r.ID,
		JudgeId:        r.JudgeID,
		Status:         r.Status,
		TotalCount:     int32(r.TotalCount),
		CompletedCount: int32(r.CompletedCount),
		FailedCount:    int32(r.FailedCount),
		PassRate:        float32(r.PassRate),
		CreatedAt:      r.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
		UpdatedAt:      r.UpdatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

func datasetToProto(d *types.DatasetDTO) *experimentv1.DatasetDTO {
	if d == nil {
		return nil
	}
	return &experimentv1.DatasetDTO{
		Id:          d.ID,
		UserId:      d.UserID,
		Name:        d.Name,
		Description: d.Description,
		ItemCount:   int32(d.ItemCount),
		CreatedAt:   d.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
		UpdatedAt:   d.UpdatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

func evaluationToProto(d *types.EvaluationDTO) *experimentv1.EvaluationDTO {
	if d == nil {
		return nil
	}
	return &experimentv1.EvaluationDTO{
		Id:             d.ID,
		UserId:         d.UserID,
		Name:           d.Name,
		DatasetId:      d.DatasetID,
		ModelName:      d.ModelName,
		ApikeyId:       d.APIKeyID,
		Status:         d.Status,
		TotalCount:     int32(d.TotalCount),
		CompletedCount: int32(d.CompletedCount),
		FailedCount:    int32(d.FailedCount),
		AvgScore:       float32(d.AvgScore),
		CreatedAt:      d.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
		UpdatedAt:      d.UpdatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

func evalResultToProto(r *types.EvaluationResultDTO) *experimentv1.EvaluationResultDTO {
	return &experimentv1.EvaluationResultDTO{
		Id:           r.ID,
		EvaluationId: r.EvaluationID,
		ItemId:       r.ItemID,
		ModelOutput:  r.ModelOutput,
		Score:        float32(r.Score),
		DurationMs:   r.DurationMs,
		Success:      r.Success,
		ErrorMessage: r.ErrorMessage,
		CreatedAt:    r.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
}

// --- Annotation ---

func (s *GRPCService) GetAnnotation(ctx context.Context, req *experimentv1.GetAnnotationRequest) (*experimentv1.AnnotationResponse, error) {
	dto, err := s.annotationSvc.GetAnnotation(req.UserId, req.TraceId, req.LogId)
	if err != nil {
		log.Printf("[ERROR] grpc_service: GetAnnotation failed uid=%d trace=%d log=%d: %v", req.UserId, req.TraceId, req.LogId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.AnnotationResponse{Annotation: annotationToProto(dto)}, nil
}

func (s *GRPCService) SaveAnnotation(ctx context.Context, req *experimentv1.SaveAnnotationRequest) (*experimentv1.AnnotationResponse, error) {
	// Convert proto feedbacks to internal types
	feedbacks := make([]types.FeedbackItem, 0, len(req.Feedbacks))
	for _, fb := range req.Feedbacks {
		feedbacks = append(feedbacks, types.FeedbackItem{
			Name:   fb.Name,
			Passed: fb.Passed,
			Reason: fb.Reason,
			Source: fb.Source,
		})
	}

	// Convert proto expectation to internal type
	var expectation *types.ExpectationItem
	if req.Expectation != nil && req.Expectation.Name != "" {
		expectation = &types.ExpectationItem{
			Name:     req.Expectation.Name,
			DataType: req.Expectation.DataType,
			Content:  req.Expectation.Content,
			Reason:   req.Expectation.Reason,
		}
	}

	dto, err := s.annotationSvc.SaveAnnotation(req.UserId, req.TraceId, req.LogId, types.SaveAnnotationRequest{
		Feedbacks:   feedbacks,
		Expectation: expectation,
	})
	if err != nil {
		log.Printf("[ERROR] grpc_service: SaveAnnotation failed uid=%d trace=%d log=%d: %v", req.UserId, req.TraceId, req.LogId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}
	return &experimentv1.AnnotationResponse{Annotation: annotationToProto(dto)}, nil
}

func annotationToProto(d *types.AnnotationDTO) *experimentv1.AnnotationDTO {
	if d == nil {
		return nil
	}
	proto := &experimentv1.AnnotationDTO{
		Id:        d.ID,
		UserId:    d.UserID,
		TraceId:   d.TraceID,
		LogId:     d.LogID,
		CreatedAt: d.CreatedAt.UTC().Format("2006-01-02T15:04:05Z"),
		UpdatedAt: d.UpdatedAt.UTC().Format("2006-01-02T15:04:05Z"),
	}
	for _, fb := range d.Feedbacks {
		proto.Feedbacks = append(proto.Feedbacks, &experimentv1.FeedbackItem{
			Name:   fb.Name,
			Passed: fb.Passed,
			Reason: fb.Reason,
			Source: fb.Source,
		})
	}
	if d.Expectation != nil {
		proto.Expectation = &experimentv1.ExpectationItem{
			Name:     d.Expectation.Name,
			DataType: d.Expectation.DataType,
			Content:  d.Expectation.Content,
			Reason:   d.Expectation.Reason,
		}
	}
	return proto
}

func (s *GRPCService) BatchGetAnnotationSummaries(ctx context.Context, req *experimentv1.BatchGetAnnotationSummariesRequest) (*experimentv1.BatchGetAnnotationSummariesResponse, error) {
	summaries, err := s.annotationSvc.BatchGetSummaries(req.UserId, req.TraceId, req.LogIds)
	if err != nil {
		log.Printf("[ERROR] grpc_service: BatchGetAnnotationSummaries failed uid=%d trace=%d: %v", req.UserId, req.TraceId, err)
		return nil, status.Error(codes.Internal, err.Error())
	}

	protoMap := make(map[uint64]*experimentv1.AnnotationSummary, len(summaries))
	for logID, s := range summaries {
		protoMap[logID] = &experimentv1.AnnotationSummary{
			LogId:          s.LogID,
			HasFeedback:    s.HasFeedback,
			FeedbackPassed: s.FeedbackPassed,
			FeedbackCount:  int32(s.FeedbackCount),
			HasExpectation: s.HasExpectation,
		}
	}

	return &experimentv1.BatchGetAnnotationSummariesResponse{Summaries: protoMap}, nil
}
