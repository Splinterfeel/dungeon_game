using DungeonClient.App;
using DungeonClient.Battle;
using DungeonClient.Screens;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UIElements;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace DungeonClient.Editor
{
    /// <summary>
    /// Одна и та же команда используется из меню редактора и Unity CLI.
    /// </summary>
    public static class ProjectBootstrap
    {
        private const string SceneFolder = "Assets/DungeonClient/Scenes";
        private const string ScenePath = SceneFolder + "/Bootstrap.unity";
        private const string UiFolder = "Assets/DungeonClient/UI";
        private const string PilotDocumentPath = UiFolder + "/PilotSelection.uxml";
        private const string PilotStylePath = UiFolder + "/PilotSelection.uss";
        private const string GarageDocumentPath = UiFolder + "/Garage.uxml";
        private const string GarageStylePath = UiFolder + "/Garage.uss";
        private const string PanelSettingsPath = UiFolder + "/DungeonPanelSettings.asset";

        [MenuItem("Dungeon Client/Создать стартовую сцену")]
        public static void CreateBaseScene()
        {
            EnsureFolder("Assets/DungeonClient");
            EnsureFolder(SceneFolder);
            EnsureFolder(UiFolder);

            var scene = EditorSceneManager.NewScene(
                NewSceneSetup.EmptyScene,
                NewSceneMode.Single
            );
            CreateCamera();
            CreateLight();

            var app = new GameObject("DungeonClient");
            app.AddComponent<ClientApp>();
            var panelSettings = GetOrCreatePanelSettings();
            CreatePilotScreen(app.transform, panelSettings);
            CreateGarageScreen(app.transform, panelSettings);
            CreateLobbyScreen(app.transform, panelSettings);
            CreateBattleScreen(app.transform, panelSettings);

            EditorSceneManager.SaveScene(scene, ScenePath);
            EditorBuildSettings.scenes = new[]
            {
                new EditorBuildSettingsScene(ScenePath, true),
            };
            AssetDatabase.SaveAssets();
            Debug.Log("Стартовая сцена DungeonClient создана.");
        }

        private static void CreatePilotScreen(Transform parent, PanelSettings panelSettings)
        {
            var screen = new GameObject("PilotSelectionScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = panelSettings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(
                PilotDocumentPath
            );
            var controller = screen.AddComponent<PilotSelectionScreen>();
            controller.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(PilotStylePath));
        }

        [MenuItem("Dungeon Client/Добавить экран лобби")]
        public static void AddLobbyToOpenScene()
        {
            if (Object.FindFirstObjectByType<LobbyScreen>() != null) return;
            var app = Object.FindFirstObjectByType<ClientApp>();
            if (app == null) throw new System.InvalidOperationException("Не найден ClientApp");
            var pilot = Object.FindFirstObjectByType<PilotSelectionScreen>();
            CreateLobbyScreen(app.transform, pilot.GetComponent<UIDocument>().panelSettings);
            EditorSceneManager.MarkSceneDirty(app.gameObject.scene);
            EditorSceneManager.SaveScene(app.gameObject.scene);
        }

        private static void CreateLobbyScreen(Transform parent, PanelSettings settings)
        {
            var screen = new GameObject("LobbyScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = settings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(UiFolder + "/Lobby.uxml");
            screen.AddComponent<LobbyScreen>().SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(UiFolder + "/Lobby.uss"));
        }

        private static void CreateGarageScreen(Transform parent, PanelSettings panelSettings)
        {
            var screen = new GameObject("GarageScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = panelSettings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(
                GarageDocumentPath
            );
            var controller = screen.AddComponent<GarageScreen>();
            controller.SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(GarageStylePath));
        }

        [MenuItem("Dungeon Client/Добавить экран боя")]
        public static void AddBattleToOpenScene()
        {
            if (Object.FindAnyObjectByType<BattleScreen>() != null) return;
            var app = Object.FindAnyObjectByType<ClientApp>();
            if (app == null) throw new System.InvalidOperationException("Не найден ClientApp");
            var pilot = Object.FindAnyObjectByType<PilotSelectionScreen>();
            CreateBattleScreen(app.transform, pilot.GetComponent<UIDocument>().panelSettings);
            EditorSceneManager.MarkSceneDirty(app.gameObject.scene);
            EditorSceneManager.SaveScene(app.gameObject.scene);
        }

        private static void CreateBattleScreen(Transform parent, PanelSettings settings)
        {
            var screen = new GameObject("BattleScreen");
            screen.transform.SetParent(parent, false);
            var document = screen.AddComponent<UIDocument>();
            document.panelSettings = settings;
            document.visualTreeAsset = AssetDatabase.LoadAssetAtPath<VisualTreeAsset>(UiFolder + "/Battle.uxml");
            var surface = BattleMaterial("BattleSurface", "Universal Render Pipeline/Lit");
            var marker = BattleMaterial("BattleMarker", "Universal Render Pipeline/Unlit");
            screen.AddComponent<BattleArenaView>().Configure(surface, marker);
            screen.AddComponent<BattleScreen>().SetStyleSheet(AssetDatabase.LoadAssetAtPath<StyleSheet>(UiFolder + "/Battle.uss"));
        }

        private static Material BattleMaterial(string name, string shaderName)
        {
            var path = UiFolder + "/" + name + ".mat";
            var material = AssetDatabase.LoadAssetAtPath<Material>(path);
            if (material != null) return material;
            var shader = Shader.Find(shaderName);
            if (shader == null) throw new System.InvalidOperationException("Не найден шейдер " + shaderName);
            material = new Material(shader);
            AssetDatabase.CreateAsset(material, path);
            return material;
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            var parent = System.IO.Path.GetDirectoryName(path)?.Replace("\\", "/");
            var folderName = System.IO.Path.GetFileName(path);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(folderName))
            {
                throw new System.InvalidOperationException($"Не удалось создать папку {path}");
            }

            AssetDatabase.CreateFolder(parent, folderName);
        }

        private static void CreateCamera()
        {
            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            cameraObject.transform.position = new Vector3(0f, 8f, -8f);
            cameraObject.transform.rotation = Quaternion.Euler(35f, 0f, 0f);

            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.04f, 0.06f, 0.09f);
        }

        private static void CreateLight()
        {
            var lightObject = GameObject.Find("Directional Light") ?? new GameObject("Directional Light");
            lightObject.transform.rotation = Quaternion.Euler(48f, -35f, 0f);
            var light = lightObject.GetComponent<Light>();
            if (light == null) light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = new Color(1f, .88f, .74f);
            light.intensity = 1.65f;
            light.shadows = LightShadows.Soft;
            light.shadowStrength = .78f;
            light.shadowBias = .03f;
            light.shadowNormalBias = .18f;
            light.GetUniversalAdditionalLightData().usePipelineSettings = false;
            RenderSettings.sun = light;

            var fillObject = GameObject.Find("Battle Fill Light") ?? new GameObject("Battle Fill Light");
            fillObject.transform.rotation = Quaternion.Euler(32f, 145f, 0f);
            var fill = fillObject.GetComponent<Light>();
            if (fill == null) fill = fillObject.AddComponent<Light>();
            fill.type = LightType.Directional;
            fill.color = new Color(.48f, .67f, 1f);
            fill.intensity = .45f;
            fill.shadows = LightShadows.None;

            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = new Color(.28f, .34f, .48f);
            RenderSettings.ambientEquatorColor = new Color(.16f, .19f, .26f);
            RenderSettings.ambientGroundColor = new Color(.07f, .085f, .12f);
            RenderSettings.ambientIntensity = 1f;
            // В общем обзоре карты тени тоже остаются видны.
            var pipeline = AssetDatabase.LoadAssetAtPath<UniversalRenderPipelineAsset>("Assets/Settings/PC_RPAsset.asset");
            if (pipeline != null)
            {
                pipeline.shadowDistance = 85f;
                EditorUtility.SetDirty(pipeline);
            }
            DynamicGI.UpdateEnvironment();
        }

        [MenuItem("Dungeon Client/Обновить освещение арены")]
        public static void ApplyBattleLightingToOpenScene()
        {
            if (EditorApplication.isPlaying) throw new System.InvalidOperationException("Сохранять освещение нужно вне Play Mode");
            CreateLight();
            var scene = SceneManager.GetActiveScene();
            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
        }

        private static PanelSettings GetOrCreatePanelSettings()
        {
            var panelSettings = AssetDatabase.LoadAssetAtPath<PanelSettings>(PanelSettingsPath);
            if (panelSettings != null)
            {
                return panelSettings;
            }

            panelSettings = ScriptableObject.CreateInstance<PanelSettings>();
            panelSettings.scaleMode = PanelScaleMode.ScaleWithScreenSize;
            panelSettings.referenceResolution = new Vector2Int(1280, 720);
            panelSettings.screenMatchMode = PanelScreenMatchMode.Expand;
            AssetDatabase.CreateAsset(panelSettings, PanelSettingsPath);
            return panelSettings;
        }
    }
}
