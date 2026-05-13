import type { DRISignals, DRIResult, DRIStage } from '../types';

const WEIGHTS: Record<keyof DRISignals, number> = {
  searchSpike: 0.15,
  commentAttackVelocity: 0.15,
  toxicityDuplication: 0.15,
  harmfulContentExposure: 0.20,
  newsSNSAmplification: 0.10,
  manipulationSignal: 0.10,
  economicDisruptionSignal: 0.15,
};

function getStage(score: number): DRIStage {
  if (score < 40) return 'Normal';
  if (score < 60) return 'Watch';
  if (score < 75) return 'Alert';
  if (score < 90) return 'Trigger';
  return 'Severe';
}

// 나중에 실제 raw 데이터(YouTube API, Naver API 결과)를 받아
// 각 signal 점수를 계산하는 로직으로 교체한다.
export function calculateDRI(signals: DRISignals): DRIResult {
  const score = Math.round(
    Object.entries(signals).reduce((acc, [key, value]) => {
      return acc + value * WEIGHTS[key as keyof DRISignals];
    }, 0)
  );

  const signalDetails = [
    {
      label: 'Search Spike',
      score: signals.searchSpike,
      weight: WEIGHTS.searchSpike,
      description: 'Google Trends 검색 관심도 급증 탐지',
      subFactors: ['크리에이터명 검색량', '논란 키워드 연관 검색', '지속 기간'],
    },
    {
      label: 'Comment Attack Velocity',
      score: signals.commentAttackVelocity,
      weight: WEIGHTS.commentAttackVelocity,
      description: '댓글 증가 속도 및 Z-score 분석',
      subFactors: ['시간당 댓글 증가율', '베이스라인 대비 Z-score', '집중 공격 여부'],
    },
    {
      label: 'Toxicity & Duplication',
      score: signals.toxicityDuplication,
      weight: WEIGHTS.toxicityDuplication,
      description: '독성 댓글·부정 스탠스·중복 패턴 탐지',
      subFactors: [
        '욕설·모욕·협박성 댓글 비율',
        '부정 스탠스 비율',
        '동일 문구 반복률',
        '유사 댓글 군집 수',
        '외국어·비정상 패턴',
      ],
    },
    {
      label: 'Harmful Content Exposure',
      score: signals.harmfulContentExposure,
      weight: WEIGHTS.harmfulContentExposure,
      description: '제3자 영상·게시글 노출 규모',
      subFactors: ['관련 영상 수', '총 조회수', '사이버렉카 포함 여부', '확산 속도'],
    },
    {
      label: 'News / SNS Amplification',
      score: signals.newsSNSAmplification,
      weight: WEIGHTS.newsSNSAmplification,
      description: '뉴스·SNS·커뮤니티 확산 규모',
      subFactors: ['뉴스 기사 수', 'SNS 언급량', '커뮤니티 게시물', '블로그 확산'],
    },
    {
      label: 'Manipulation Signal',
      score: signals.manipulationSignal,
      weight: WEIGHTS.manipulationSignal,
      description: '조직적 공격·여론 조작 패턴 탐지',
      subFactors: ['반복 계정 패턴', '유사 문구 군집', '비정상 계정 비율'],
    },
    {
      label: 'Economic Disruption Signal',
      score: signals.economicDisruptionSignal,
      weight: WEIGHTS.economicDisruptionSignal,
      description: '조회수 하락·업로드 공백·수익 변동 신호',
      subFactors: ['조회수 변화율', '업로드 공백 기간', '후원·멤버십 변동', '광고 중단 여부'],
    },
  ];

  return {
    score,
    stage: getStage(score),
    signals,
    signalDetails,
  };
}
