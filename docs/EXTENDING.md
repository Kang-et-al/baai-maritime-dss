# 변경·확장 가이드

## 파라미터 변경

`configs/baseline.json`을 다른 이름으로 복사해 수정한 뒤 `--config`로 지정한다. 비용계수, 납기 배수, 실제 태풍 경유점, 예측 편향, 파고 생성 파라미터는 기존 코드 변경 없이 조정할 수 있다. 일부 항목만 담은 JSON도 허용하며 나머지는 기본값을 쓴다.

속도·감속계수·시간층 변경은 2단계 이동시간이 정확히 정수 시간층으로 나뉘어야 한다. 현재 구현은 이에 어긋나는 설정을 조용히 올림하지 않고 오류로 거부한다. 롤링 주기는 기상 시계 정합성을 위해 정수 시간으로 제한한다.

## 예측기 교체

`generate(observation, config) -> Forecast`를 구현한다. 입력 observation에는 공개된 구간만 존재한다. 새 예측기가 숨겨진 실제 World를 읽지 않도록 유지한다. 반환 Forecast는 상대적으로 같은 시간격자의 상태 배열 [시나리오,시간,3], 라벨, 양의 확률 벡터를 제공해야 한다. 첫 rolling_h 구간은 모든 시나리오에서 동일하고 공개 실제 상태와 일치해야 한다.

Python에서 `Simulation(config, output, forecaster=새예측기())`로 주입한다. AI는 우선 자연어→검증된 경유점/파라미터 변환 단계에 연결할 수 있다. 실험 실행 도중 매번 LLM 호출이 필요한 구조는 아니다.

## 의사결정 모델 교체

`planner_factory(network, config, due_h)`를 `Simulation`에 주입한다. 반환 객체는 `solve(node_id, now, forecast)`를 제공하고 기존 plan JSON 스키마를 반환해야 한다. 스키마는 생성된 steps JSON과 `TwoStagePlanner.solve`를 참고한다. 시뮬레이터는 최적화 내부를 알 필요 없이 first_actions만 실행한다.

## 기상과 비용 확장

- 파고 공간장은 `weather.wave`, 감속/속도상한은 `weather.speed_rule`.
- 대기 안전성은 planner와 execution 양쪽에서 동일하게 반영한다.
- 연료식은 `planner.fuel_rate`, 비용은 `planner.action_cost`.
- 실제 실행비용과 계획비용 일치 검사를 유지한다.
- 풍향·해류를 추가하면 정수 시간층 가정이 달라질 수 있다. 그때 시간 이산화 방법부터 별도 논의한다.

## 시나리오 수 변경

수치 DP와 보고서는 Forecast의 시나리오 개수를 사용한다. `representative_index`로 강조할 대표 시나리오를 지정한다(기본값 4, 0부터 시작). `Forecast.validate`가 확률합·배열크기·공통구간·강도범위·대표 인덱스를 검사한다. 동일 기상 시나리오는 후방 DP를 한 번만 계산해 같은 결과를 공유한다.

## 회귀검증

수치모델 변경 후 `python -m unittest discover -s tests -v`를 실행한다. 작은 네트워크의 독립 완전열거 결과와 후방 DP를 비교한다. 실제 네트워크에서는 calm 끝까지 실행과 typhoon 여러 스텝을 확인한다. 기존 결과를 이어가며 코드 변경 전후를 섞지 않는다.
