import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { OngletModuleo } from "@/onglets/OngletModuleo";

// Onglet Outils du Panel (spec 1.5.3) : un sous-onglet par outil, Moduléo
// seul pour l'instant.
export function OngletOutils() {
  return (
    <Tabs defaultValue="moduleo">
      <TabsList>
        <TabsTrigger value="moduleo">Moduléo</TabsTrigger>
      </TabsList>
      <TabsContent value="moduleo">
        <OngletModuleo />
      </TabsContent>
    </Tabs>
  );
}
